"""A small, hand-made demo match for frontend work against the local API.

Not the official demo data: B02 owns the `demo-1021` preset and the simulator output will
replace this. Everything here is fictional and deterministic, so the web app always sees the
same match, momentum curve and pivots.
"""

from __future__ import annotations

import math

from pivot_core.domain import (
    Claim,
    Coach,
    Competition,
    ExplanationSentence,
    LineupSlot,
    Match,
    MatchContext,
    MatchEvent,
    MinuteMetric,
    Narrative,
    PeriodInfo,
    Personality,
    Pivot,
    Player,
    PlayerAttributes,
    Score,
    StatRef,
    Team,
    TeamSheet,
    TeamTactics,
    ViewerPrefs,
)
from pivot_core.ports import MatchRepository

DEMO_MATCH_ID = "M-api-demo"
HALF = 45 * 60
NOW_MINUTE = 75                       # the demo match is live, 75 minutes in

ROLES_433 = ["GK", "RB", "CB", "CB", "LB", "DM", "CM", "CM", "RW", "ST", "LW"]
ANCHORS_433 = [(4, 34), (30, 8), (25, 25), (25, 43), (30, 60), (40, 34), (50, 22), (50, 46),
               (72, 10), (78, 34), (72, 58)]
PERSONALITY = Personality(**{f: 60 for f in Personality.model_fields})


def _attributes(base: int) -> PlayerAttributes:
    def group(*names: str) -> dict:
        return {n: base for n in names}
    return PlayerAttributes(
        attacking=group("crossing", "finishing", "heading_accuracy", "short_passing", "volleys"),
        skill=group("dribbling", "curve", "free_kick_accuracy", "long_passing", "ball_control"),
        movement=group("acceleration", "sprint_speed", "agility", "reactions", "balance"),
        power=group("shot_power", "jumping", "stamina", "strength", "long_shots"),
        mentality=group("aggression", "interceptions", "attack_positioning", "vision", "penalties",
                        "composure"),
        defending=group("defensive_awareness", "standing_tackle", "sliding_tackle"),
        goalkeeping=group("diving", "handling", "kicking", "positioning", "reflexes"),
    )


def _team(side: str, name: str, short: str, color: str, surnames: list[str]) -> Team:
    roles = ROLES_433 + ["GK", "CB", "CM", "ST"]
    squad = [Player(player_id=f"{side[0]}{n:02d}", name=f"{surnames[n - 1][0]}. {surnames[n - 1]}", team=side,
                    shirt_number=n, role=role, age=22 + n % 10, nationality="Freeland", height_cm=178,
                    weight_kg=74, attributes=_attributes(64 + n % 12), personality=PERSONALITY)
             for n, role in enumerate(roles, start=1)]
    pid = [p.player_id for p in squad]
    sheet = TeamSheet(
        formation="4-3-3",
        starters=[LineupSlot(player_id=pid[i], slot=i + 1, role=r, anchor=ANCHORS_433[i])
                  for i, r in enumerate(ROLES_433)],
        bench=pid[11:], captain_id=pid[5], penalty_taker_id=pid[9], free_kick_taker_id=pid[6],
        corner_taker_left_id=pid[8], corner_taker_right_id=pid[10],
    )
    coach = Coach(coach_id=f"{side[0]}-coach", name=f"{surnames[-1][0]}. {surnames[-1]}", age=50,
                  nationality="Freeland", style="balanced", preferred_formation="4-3-3",
                  attributes={"tactical_knowledge": 75, "in_game_adaptability": 70,
                              "man_management": 68, "motivation": 72},
                  personality=PERSONALITY)
    return Team(side=side, club_id=f"club-{short.lower()}", name=name, short_name=short, color=color,
                coach=coach, squad=squad, sheet=sheet, tactics=TeamTactics())


HOME_NAMES = ["Varga", "Okafor", "Lindqvist", "Moreno", "Hale", "Brandt", "Ishikawa", "Duarte", "Kowal",
              "Mensah", "Rossi", "Pike", "Ndiaye", "Haddad", "Quint", "Arden"]
AWAY_NAMES = ["Sorensen", "Bakker", "Oyelaran", "Castell", "Reyes", "Novak", "Fenwick", "Aziz", "Lemaire",
              "Tanaka", "Obi", "Marsh", "Ruiz", "Holm", "Petrov", "Calloway"]

# (minute, second, side, type, player, extra fields): the moments that matter in the demo story.
KEY_MOMENTS = [
    (23, 12, "home", "shot", "h10", {"shot_outcome": "goal", "xg": 0.31, "location": (93.0, 30.0),
                                     "end_location": (105.0, 33.5), "body_part": "right_foot"}),
    (38, 40, "away", "card", "a06", {"meta": {"card": "yellow"}}),
    (61, 5, "away", "substitution", "a10", {}),
    (64, 30, "away", "shot", "a15", {"shot_outcome": "goal", "xg": 0.22, "location": (14.0, 40.0),
                                     "end_location": (0.0, 35.0), "body_part": "left_foot"}),
    (71, 50, "away", "shot", "a09", {"shot_outcome": "goal", "xg": 0.44, "location": (9.0, 33.0),
                                     "end_location": (0.0, 33.0), "body_part": "head"}),
]


def _clock(t: int) -> dict:
    return {"t": t, "period": 1, "period_t": t} if t < HALF else {"t": t, "period": 2, "period_t": t - HALF}


def demo_events() -> list[MatchEvent]:
    """Two kick-offs, a pass every 30 seconds and the key moments, up to NOW_MINUTE."""
    raw: list[tuple[int, str, str, str | None, dict]] = [(0, "home", "kickoff", "h10", {}),
                                                          (HALF, "away", "kickoff", "a10", {})]
    for t in range(15, NOW_MINUTE * 60, 30):
        side = "home" if (t // 30) % 3 else "away"
        n = 2 + (t // 30) % 9
        x = 30.0 + (t // 30) % 40
        raw.append((t, side, "pass", f"{side[0]}{n:02d}",
                    {"location": (x, 34.0), "end_location": (min(x + 12, 105.0), 28.0), "outcome": "success",
                     "receiver_id": f"{side[0]}{n + 1:02d}", "pass_type": "regular", "pass_height": "ground"}))
    for minute, second, side, kind, player, extra in KEY_MOMENTS:
        raw.append((minute * 60 + second, side, kind, player, extra))
    raw.sort(key=lambda r: r[0])

    events = []
    for seq, (t, side, kind, player, extra) in enumerate(raw):
        if kind == "substitution":
            extra = {"substitution": {"player_off_id": "a10", "player_on_id": "a15", "slot": 10,
                                      "reason": "tactical"}}
        events.append(MatchEvent(match_id=DEMO_MATCH_ID, seq=seq, event_id=f"m{t // 60:03d}-s{seq:05d}",
                                 type=kind, team=side, player_id=player, **_clock(t), **extra))
    return events


def demo_metrics() -> list[MinuteMetric]:
    """Home on top early, away take over after the 61st-minute substitution."""
    metrics = []
    for minute in range(NOW_MINUTE):
        trend = 0.35 if minute < 61 else -0.45
        momentum = max(-1.0, min(1.0, trend + 0.25 * math.sin(minute / 4)))
        metrics.append(MinuteMetric(
            match_id=DEMO_MATCH_ID, minute=minute, momentum=round(momentum, 3),
            threat_home=round(max(0.0, 0.05 + momentum * 0.08), 3),
            threat_away=round(max(0.0, 0.05 - momentum * 0.08), 3),
            pressure_home=3 + round(4 * max(momentum, 0)), pressure_away=3 + round(4 * max(-momentum, 0)),
        ))
    return metrics


def demo_pivots(events: list[MatchEvent]) -> list[Pivot]:
    ids = {(e.type, e.minute): e.event_id for e in events}
    sub, goal = ids[("substitution", 61)], ids[("shot", 64)]
    narrative = Narrative(
        prefs=ViewerPrefs(), headline="Rovers seize control after the change", source="llm", verifier_attempts=1,
        sentences=[
            ExplanationSentence(
                text="Rovers levelled within minutes of the substitution, with their only shot of the spell.",
                evidence_ids=[sub, goal],
                claims=[Claim(value=1, unit="count", stat_ref=StatRef(metric="shots", team="away", window=(61, 66)))],
            ),
        ],
    )
    return [
        Pivot(pivot_id=f"{DEMO_MATCH_ID}:p61", match_id=DEMO_MATCH_ID, minute=61, direction="away", severity=2,
              status="confirmed", trigger_event_ids=[sub, goal], narrative=narrative, chain_id="c-demo-61"),
        Pivot(pivot_id=f"{DEMO_MATCH_ID}:p71", match_id=DEMO_MATCH_ID, minute=71, direction="away", severity=1,
              status="pending", trigger_event_ids=[ids[("shot", 71)]], chain_id="c-demo-71"),
    ]


def demo_match() -> Match:
    return Match(
        match_id=DEMO_MATCH_ID, seed=20261023, home=_team("home", "Harbour City", "HBC", "#1E6B45", HOME_NAMES),
        away=_team("away", "Northgate Rovers", "NGR", "#B3261E", AWAY_NAMES),
        context=MatchContext(
            competition=Competition(competition_id="fl-1", name="Freeland League", level="league", importance=3),
            venue="Harbour Park", attendance=38200,
        ),
        status="live", clock=NOW_MINUTE * 60, period=2,
        periods=[PeriodInfo(period=1, start_t=0, end_t=HALF), PeriodInfo(period=2, start_t=HALF)],
        score=Score(home=1, away=2),
    )


async def seed_demo(repo: MatchRepository) -> str:
    """Store the demo match with its events, metrics and pivots. Safe to call twice."""
    events = demo_events()
    await repo.upsert_match(demo_match())
    await repo.append_events(events)
    await repo.upsert_metrics(demo_metrics())
    for pivot in demo_pivots(events):
        await repo.upsert_pivot(pivot)
    return DEMO_MATCH_ID
