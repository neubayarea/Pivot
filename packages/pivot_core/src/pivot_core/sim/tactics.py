"""Each coach's own plan (Bx13): a style per coach and team tactics that follow it.

`build_team` gives every coach the "balanced" style and every team the default `TeamTactics`, so
both sides of a match play the same way. `styled(match)` gives each coach a style drawn from the
match seed (the better side is a little more likely to attack) and turns it into tactics:

- the style sets the press, the back line, the tempo and the passing: defensive teams sit low,
  press little and go direct; attacking teams hold a high line, press high and pass short;
- the coach's formation moves the width: wingers make a defensive or attacking side wider, five at
  the back narrower (a balanced side plays normal width, the engine's default);
- the squad sets the rest: the attack goes down the flank with the better wide players, corners
  curl in or out by the takers' feet, and free kicks go direct when the taker is good at them.

Every value is one the what-if lab can already pick, so the engine stays within the ranges it
was tuned on (docs/sim-realism.md). The same seed always gives the same plans. The two demo clubs
of the season (`world.py`) and the recorded demo keep the default tactics; the site's seed
matches (`pivot_api.sims`) play by these.
"""

from __future__ import annotations

import numpy as np

from ..domain import Match, Player, SetPieceTactics, Team, TeamTactics

STYLES = ("defensive", "balanced", "attacking")
STYLE_ODDS = (0.3, 0.4, 0.3)
QUALITY_TILT = 0.2                    # a side 10 rating points better: +0.2 attacking, -0.2 defensive
WIDTHS = ("narrow", "normal", "wide")
LEFT, RIGHT = {"LB", "LWB", "LM", "LW"}, {"RB", "RWB", "RM", "RW"}
# The engine is tuned on a mid line, and a side sits as deep when behind as when ahead: a low or high
# line on every defensive or attacking side puts corners and the leader's share of shots out of range
# (scripts/realism_scorecard.py --styled), so only some of them hold one.
LOW_LINE, HIGH_LINE = (0.25, 0.75), (0.4, 0.6)
FLANK_GAP = 3.0                       # rating points between the flanks before the attack favours one


def styled(match: Match) -> Match:
    """The match with each coach's style and the team tactics that follow from it."""
    quality = [_quality(t) for t in (match.home, match.away)]
    teams = []
    for k, team in enumerate((match.home, match.away)):
        rng = np.random.default_rng([match.seed or 0, k, 13])
        style = pick_style(rng, quality[k] - quality[1 - k])
        coach = team.coach.model_copy(update={"style": style})
        teams.append(team.model_copy(update={"coach": coach, "tactics": coach_tactics(rng, team, style)}))
    return match.model_copy(update={"home": teams[0], "away": teams[1]})


def pick_style(rng: np.random.Generator, gap: float) -> str:
    tilt = QUALITY_TILT * float(np.clip(gap / 10, -1, 1))
    odds = np.array([STYLE_ODDS[0] - tilt, STYLE_ODDS[1], STYLE_ODDS[2] + tilt])
    return str(rng.choice(STYLES, p=odds / odds.sum()))


def coach_tactics(rng: np.random.Generator, team: Team, style: str) -> TeamTactics:
    roles = {s.role for s in team.sheet.starters}
    by_id = {p.player_id: p for p in team.squad}
    starters = [by_id[s.player_id] for s in team.sheet.starters]
    if style == "defensive":
        plan = dict(line_height=_pick(rng, ("low", "mid"), LOW_LINE), press=_pick(rng, ("low", "mid"), (0.7, 0.3)),
                    tempo="slow",
                    passing=_pick(rng, ("direct", "mixed"), (0.6, 0.4)), counter_attack=True, time_wasting=True)
        width = 0
    elif style == "attacking":
        plan = dict(line_height=_pick(rng, ("high", "mid"), HIGH_LINE), press=_pick(rng, ("high", "mid"), (0.75, 0.25)),
                    tempo=_pick(rng, ("fast", "normal"), (0.6, 0.4)), passing="short",
                    offside_trap=bool(rng.random() < 0.5))
        width = 1
    else:
        plan = dict(line_height="mid", press="mid", tempo="normal",
                    passing=_pick(rng, ("mixed", "short", "direct"), (0.6, 0.2, 0.2)),
                    counter_attack=bool(rng.random() < 0.3))
        width = 1
    wingers = style != "balanced" and ("LW" in roles or "RW" in roles)
    width += wingers - (team.sheet.formation.startswith("5") or "LWB" in roles)
    return TeamTactics(**plan, width=WIDTHS[int(np.clip(width, 0, 2))], attack_focus=_focus(starters, roles),
                       set_pieces=_set_pieces(team, by_id, starters, style))


def _pick(rng: np.random.Generator, options: tuple[str, ...], odds: tuple[float, ...]) -> str:
    return str(rng.choice(options, p=odds))


def _quality(team: Team) -> float:
    by_id = {p.player_id: p for p in team.squad}
    return float(np.mean([_overall(by_id[s.player_id]) for s in team.sheet.starters]))


def _overall(p: Player) -> float:
    groups = p.attributes.model_dump()
    if p.role != "GK":
        groups.pop("goalkeeping")
    return float(np.mean([v for g in groups.values() for v in g.values()]))


def _wide(p: Player) -> float:
    a = p.attributes
    return (a.attacking.crossing + a.skill.dribbling + a.movement.sprint_speed) / 3


def _focus(starters: list[Player], roles: set[str]) -> str:
    """The flank with the better wide players, else the middle when there is a playmaker or a strike pair."""
    left = [_wide(p) for p in starters if p.role in LEFT]
    right = [_wide(p) for p in starters if p.role in RIGHT]
    gap = (np.mean(left) if left else 0.0) - (np.mean(right) if right else 0.0)
    if gap > FLANK_GAP:
        return "left"
    if gap < -FLANK_GAP:
        return "right"
    return "centre" if "AM" in roles or sum(p.role == "ST" for p in starters) > 1 else "balanced"


def _set_pieces(team: Team, by_id: dict[str, Player], starters: list[Player], style: str) -> SetPieceTactics:
    sheet = team.sheet
    # From the left corner a right-footed taker curls the ball in towards goal, and the other way round.
    swing = {by_id[sheet.corner_taker_left_id].preferred_foot == "right",
             by_id[sheet.corner_taker_right_id].preferred_foot == "left"}
    delivery = "mixed" if len(swing) > 1 else "inswing" if swing.pop() else "outswing"
    headers = sum(p.attributes.attacking.heading_accuracy >= 70 and p.height_cm >= 185 for p in starters if p.role != "GK")
    fk = by_id[sheet.free_kick_taker_id].attributes.skill.free_kick_accuracy
    forward, back, marking = {"defensive": (4, 1, "zonal"), "balanced": (5, 1, "mixed"),
                              "attacking": (6, 2, "man")}[style]
    return SetPieceTactics(corner_delivery=delivery,
                           corner_target="far_post" if headers >= 3 else "penalty_spot" if headers == 2
                           else "near_post",
                           free_kick_style="direct" if fk >= 75 else "mixed" if fk >= 65 else "cross",
                           players_forward_on_corners=forward + (headers >= 3), corner_defence=marking,
                           players_back_on_corners=back)
