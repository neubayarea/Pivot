"""The pre-match page's numbers (Bx15, #314): records, recent games, head-to-head, what comes next, the matchup.

GET /api/matches/{id}/prematch[?team=home|away]

Counted from the season so far (eval/fixtures/season-2026.json, B13) and the match's own team sheets
and tactics. Read-only: nothing here changes the match or how the simulator plays it.

- The matchday: a seed match is the matchday `with_seed_season` (#289) draws from its seed, the
  recorded demo is matchday 30. Only league games before it count.
- Records: all games, home games only, away games only, and the table position before the match.
- Recent games: the last five, each with its half-time score. The season file keeps the elapsed
  minute of each goal, not the match clock, and the first half ends 46 to 50 minutes in, so the
  half-time score and the second-half minutes are estimated: the first half's added time is worked
  out the way the engine works it out, from the goals, substitutions and red cards in that half.
- Head-to-head: every meeting of the two clubs in the file, and those at this match's home ground.
- What comes next: the next league game comes from the season schedule; a cup tie in between is
  fictional, drawn from the match's seed. The rotation risk follows from the days and the stakes of
  that game. The usual XI is counted from the last five league games (started three or more) and
  compared with today's team sheet.
- The matchup: both formations split into flanks, midfield and each attack against the other
  side's centre-backs, and the tactics that differ. `team` picks the side the notes speak for.

Every note comes in English, with a `note_key` and `params` so the page can write it in any language.
"""

from __future__ import annotations

from collections import Counter
from functools import cache
from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request

from pivot_core.domain import Match, Team
from pivot_core.domain.common import Model
from pivot_core.sim.presets import DEMO_1021
from pivot_core.sim.season import DEMO_MATCHDAY, FIRST_SEED_MATCHDAY, table
from pivot_core.sim.world import CLUB_NAMES, HBC, ROV, SEASON, schedule

from . import sims

router = APIRouter(prefix="/api")

Side = Literal["home", "away"]
Venue = Literal["H", "A"]
Level = Literal["low", "medium", "high"]
Params = dict[str, str | int | float]

LAST = 5                                      # recent games
REGULAR = 3                                   # starts in the last five that make a regular
PERIODS = ("0-15", "16-30", "31-45", "46-60", "61-75", "76-90")
LEAGUE = "Freeland League"
LEAGUE_DAYS = 7                               # the schedule has no dates: league rounds a week apart
CUP = "Freeland Cup"
# (last matchday of the round, round, importance, chance a club is still in the cup)
CUP_ROUNDS = ((13, "Third round", "low", 0.7), (19, "Round of 16", "medium", 0.55),
              (24, "Quarter-final", "high", 0.4), (DEMO_MATCHDAY, "Semi-final", "high", 0.3))
ABOUT = ("Pre-match background from the season so far. The cup schedule is fictional and past half-time "
         "scores are estimated from goal times. None of it changes how the simulator plays the match.")


# --- the response ----------------------------------------------------------------------------------

class PrematchRecord(Model):
    played: int
    w: int
    d: int
    l: int  # noqa: E741
    gf: int
    ga: int
    pts: int
    ppg: float
    position: int | None = None               # table position before the match: overall only


class PrematchGame(Model):
    """One recent league game, seen from the team: `ft` and `ht` are [this team, opponent]."""
    season: int
    matchday: int
    opponent: str
    opponent_id: str
    venue: Venue
    ft: tuple[int, int]
    ht: tuple[int, int]
    result: Literal["W", "D", "L"]
    scored_first: bool
    came_from_behind: bool                    # was behind at some point and did not lose


class PrematchFormStats(Model):
    games: int
    gf_avg: float
    ga_avg: float
    clean_sheets: int
    failed_to_score: int
    btts: int
    over_2_5: int
    scored_first: int
    ht_lead_won: int
    ht_lead_dropped: int
    goals_by_period: dict[str, int]
    conceded_by_period: dict[str, int]
    reds: int
    avg_rating: float | None                  # the team's average player rating per game


class PrematchFixture(Model):
    competition: str
    stage: str | None                         # a cup round; None for the league
    matchday: int | None                      # league only
    opponent: str
    opponent_id: str
    venue: Venue
    days_until: int
    importance: Level
    fictional: bool                           # the cup ties are made up; the league schedule is not
    rotation_risk: Level
    rotation_note: str
    rotation_note_key: str
    rotation_params: Params


class PrematchUsualXi(Model):
    games: int                                # league games the usual XI is counted from
    regulars: list[str]                       # player ids who started REGULAR or more of them
    regulars_starting: int
    regulars_benched: list[str]
    newcomers: list[str]                      # starting today, not a regular


class PrematchTeam(Model):
    club_id: str
    name: str
    overall: PrematchRecord
    home_only: PrematchRecord
    away_only: PrematchRecord
    last5: list[PrematchGame]                 # newest first
    last5_stats: PrematchFormStats
    next_fixture: PrematchFixture | None      # the next game, cup or league
    next_league: PrematchFixture | None
    usual_xi_today: PrematchUsualXi


class PrematchH2HCount(Model):
    played: int
    home_w: int                               # wins of this match's home side
    d: int
    away_w: int


class PrematchMeeting(Model):
    """`ft` and `ht` are [home, away] of that meeting."""
    season: int
    matchday: int
    venue_club: str
    home_club: str
    away_club: str
    ft: tuple[int, int]
    ht: tuple[int, int]


class PrematchHeadToHead(Model):
    all: PrematchH2HCount
    at_this_ground: PrematchH2HCount
    meetings: list[PrematchMeeting]           # oldest first


class PrematchLine(Model):
    zone: Literal["home_wide_left", "home_wide_right", "midfield", "home_attack", "away_attack"]
    home: list[str]                           # roles
    away: list[str]
    home_players: list[str]                   # player ids, in the same order
    away_players: list[str]
    note: str
    note_key: str
    params: Params


class PrematchTacticsDiff(Model):
    field: str
    home: str
    away: str
    note: str
    note_key: str
    params: Params


class PrematchMatchup(Model):
    perspective: Side
    home_formation: str
    away_formation: str
    lines: list[PrematchLine]
    tactics_diff: list[PrematchTacticsDiff]


class PrematchReport(Model):
    match_id: str
    season: int
    matchday: int
    about: str
    about_key: str
    teams: dict[Side, PrematchTeam]
    head_to_head: PrematchHeadToHead
    matchup: PrematchMatchup


CONTRACT_MODELS = (
    PrematchRecord, PrematchGame, PrematchFormStats, PrematchFixture, PrematchUsualXi, PrematchTeam,
    PrematchH2HCount, PrematchMeeting, PrematchHeadToHead, PrematchLine, PrematchTacticsDiff, PrematchMatchup,
    PrematchReport,
)


# --- which matchday ----------------------------------------------------------------------------------

def matchday_of(match: Match) -> int | None:
    """The matchday the match is played as: 30 for the recorded demo (the season's matchday-30 fixture,
    on the demo's seed), and for a seed match the one `with_seed_season` draws (the same draw from the
    same generator); None for a match between other clubs."""
    if (match.home.club_id, match.away.club_id) != (HBC.club_id, ROV.club_id):
        return None
    if match.seed == DEMO_1021.seed:
        return DEMO_MATCHDAY
    rng = np.random.default_rng([match.seed or 0, 14])
    return int(rng.integers(FIRST_SEED_MATCHDAY, DEMO_MATCHDAY))


def before(season: dict, matchday: int) -> list[dict]:
    """This season's league games before the matchday, oldest first."""
    return sorted((r for r in season["results"] if r["season"] == SEASON and r["matchday"] < matchday),
                  key=lambda r: r["matchday"])


# --- one game ------------------------------------------------------------------------------------------

def half_time(r: dict) -> int:
    """The first elapsed minute of the second half, estimated: 45 plus the first half's added time,
    which the engine sets at 1 + 0.5 a goal + 0.25 a substitution + 0.3 a card in that half, 1 to 4
    (`sim.engine`, `_clock`; yellow cards, injuries and VAR checks are not in the file)."""
    goals = sum(g[2] < 46 for g in r["goals"])
    subs = sum(s[2] < 46 for s in r["subs_on"])
    reds = sum(c[2] < 46 for c in r["reds"])
    return 45 + int(np.clip(round(1.0 + 0.5 * goals + 0.25 * subs + 0.3 * reds), 1, 4))


def period(r: dict, minute: int) -> str:
    """The 15-minute period of an elapsed minute on the match clock; added time counts in 31-45 and 76-90."""
    ht = half_time(r)
    if minute < ht:
        return PERIODS[min(minute // 15, 2)]
    clock = minute - (ht - 45)
    return PERIODS[3 + min(max(clock - 45, 0) // 15, 2)]


def ht_score(r: dict) -> tuple[int, int]:
    """[home, away] at half-time."""
    ht = half_time(r)
    return (sum(g[0] == r["home"] and g[2] < ht for g in r["goals"]),
            sum(g[0] == r["away"] and g[2] < ht for g in r["goals"]))


def mine(pair: tuple[int, int] | list[int], r: dict, club: str) -> tuple[int, int]:
    """A [home, away] pair as [this club, opponent]."""
    return (pair[0], pair[1]) if r["home"] == club else (pair[1], pair[0])


def result(gf: int, ga: int) -> Literal["W", "D", "L"]:
    return "W" if gf > ga else "D" if gf == ga else "L"


def game(r: dict, club: str) -> PrematchGame:
    gf, ga = mine(r["score"], r, club)
    diff, behind, first = 0, False, None
    for scorer, _, _ in sorted(r["goals"], key=lambda g: g[2]):
        first = scorer == club if first is None else first
        diff += 1 if scorer == club else -1
        behind |= diff < 0
    opponent = r["away"] if r["home"] == club else r["home"]
    return PrematchGame(season=r["season"], matchday=r["matchday"], opponent=CLUB_NAMES[opponent], opponent_id=opponent,
                        venue="H" if r["home"] == club else "A", ft=(gf, ga), ht=mine(ht_score(r), r, club),
                        result=result(gf, ga), scored_first=bool(first), came_from_behind=behind and gf >= ga)


# --- records and form --------------------------------------------------------------------------------------

def record(games: list[PrematchGame], position: int | None = None) -> PrematchRecord:
    w, d, l = (sum(g.result == x for g in games) for x in "WDL")  # noqa: E741
    pts = 3 * w + d
    return PrematchRecord(played=len(games), w=w, d=d, l=l, gf=sum(g.ft[0] for g in games),
                          ga=sum(g.ft[1] for g in games), pts=pts, ppg=round(pts / len(games), 2) if games else 0.0,
                          position=position)


def form_stats(results: list[dict], club: str) -> PrematchFormStats:
    games = [game(r, club) for r in results]
    n = len(games) or 1
    scored: Counter[str] = Counter()
    conceded: Counter[str] = Counter()
    reds, ratings = 0, []
    for r in results:
        for scorer, _, minute in r["goals"]:
            (scored if scorer == club else conceded)[period(r, minute)] += 1
        reds += sum(c[0] == club for c in r["reds"])
        team = [x[2] for x in r["ratings"] if x[0] == club]
        if team:
            ratings.append(sum(team) / len(team))
    return PrematchFormStats(
        games=len(games), gf_avg=round(sum(g.ft[0] for g in games) / n, 2),
        ga_avg=round(sum(g.ft[1] for g in games) / n, 2),
        clean_sheets=sum(g.ft[1] == 0 for g in games), failed_to_score=sum(g.ft[0] == 0 for g in games),
        btts=sum(g.ft[0] > 0 and g.ft[1] > 0 for g in games), over_2_5=sum(sum(g.ft) > 2 for g in games),
        scored_first=sum(g.scored_first for g in games),
        ht_lead_won=sum(g.ht[0] > g.ht[1] and g.result == "W" for g in games),
        ht_lead_dropped=sum(g.ht[0] > g.ht[1] and g.result != "W" for g in games),
        goals_by_period={p: scored[p] for p in PERIODS}, conceded_by_period={p: conceded[p] for p in PERIODS},
        reds=reds, avg_rating=round(sum(ratings) / len(ratings), 2) if ratings else None)


def usual_xi(team: Team, results: list[dict]) -> PrematchUsualXi:
    """Who usually starts (rated and not brought on: the season's starters), against today's sheet."""
    starts: Counter[int] = Counter()
    for r in results:
        on = {s[1] for s in r["subs_on"] if s[0] == team.club_id}
        starts.update(x[1] for x in r["ratings"] if x[0] == team.club_id and x[1] not in on)
    by_shirt = {p.shirt_number: p.player_id for p in team.squad}
    regulars = [by_shirt[s] for s, k in sorted(starts.items()) if k >= REGULAR and s in by_shirt]
    today = [s.player_id for s in team.sheet.starters]
    return PrematchUsualXi(games=len(results), regulars=regulars,
                           regulars_starting=sum(p in today for p in regulars),
                           regulars_benched=[p for p in regulars if p not in today],
                           newcomers=[p for p in today if p not in regulars])


# --- what comes next ---------------------------------------------------------------------------------

@cache
def _schedule() -> dict[tuple[int, str], tuple[str, Venue]]:
    """(matchday, club) -> (opponent, venue) for every league fixture of the season."""
    out: dict[tuple[int, str], tuple[str, Venue]] = {}
    for fx in schedule():
        out[fx.matchday, fx.home] = (fx.away, "H")
        out[fx.matchday, fx.away] = (fx.home, "A")
    return out


def rotation_risk(days: int, importance: Level, stakes: str) -> Level:
    """A big game soon means rest today; a title race or a relegation fight today means less of it."""
    score = {"low": 0, "medium": 1, "high": 2}[importance] + (1 if days <= 3 else 0)
    if stakes in ("title_race", "relegation"):
        score -= 1
    return "high" if score >= 3 else "medium" if score >= 2 else "low"


def _xi_sentence(xi: PrematchUsualXi) -> str:
    n = len(xi.regulars_benched)
    if n == 0:
        return "The usual starting XI all start today."
    return f"{n} regular starter{'s' if n > 1 else ''} begin{'s' if n == 1 else ''} on the bench today."


def next_league(club: str, matchday: int, xi: PrematchUsualXi) -> PrematchFixture | None:
    if (matchday + 1, club) not in _schedule():
        return None
    opponent, venue = _schedule()[matchday + 1, club]
    name = CLUB_NAMES[opponent]
    return PrematchFixture(
        competition=LEAGUE, stage=None, matchday=matchday + 1, opponent=name, opponent_id=opponent, venue=venue,
        days_until=LEAGUE_DAYS, importance="medium", fictional=False, rotation_risk="low",
        rotation_note=f"Next league game: {name} ({'home' if venue == 'H' else 'away'}) in {LEAGUE_DAYS} days, "
                      f"no midweek game. {_xi_sentence(xi)}",
        rotation_note_key="prematch.rotation.league_" + ("benched" if xi.regulars_benched else "all_start"),
        rotation_params={"opponent": name, "venue": venue, "days": LEAGUE_DAYS, "benched": len(xi.regulars_benched)})


def cup_tie(match: Match, side: Side, matchday: int, xi: PrematchUsualXi,
            taken: tuple[str, ...] = ()) -> PrematchFixture | None:
    """A fictional midweek cup tie, drawn from the match's seed: the round follows the time of the
    season, and each club is still in the cup with that round's chance. `taken`: clubs already drawn
    against the other side in this round."""
    rng = np.random.default_rng([match.seed or 0, 314, 0 if side == "home" else 1])
    _, stage, importance, chance = next(x for x in CUP_ROUNDS if matchday <= x[0])
    alive, days, home = rng.random() < chance, int(rng.choice([3, 4])), bool(rng.random() < 0.5)
    pool = sorted(c for c in CLUB_NAMES if c not in (match.home.club_id, match.away.club_id, *taken))
    opponent = pool[int(rng.integers(len(pool)))]
    if not alive:
        return None
    name, venue = CLUB_NAMES[opponent], "H" if home else "A"
    return PrematchFixture(
        competition=CUP, stage=stage, matchday=None, opponent=name, opponent_id=opponent, venue=venue,
        days_until=days, importance=importance, fictional=True,
        rotation_risk=rotation_risk(days, importance, match.context.stakes),
        rotation_note=f"{CUP} {stage.lower()} {'at home to' if home else 'away to'} {name} in {days} days "
                      f"(fictional schedule). {_xi_sentence(xi)}",
        rotation_note_key="prematch.rotation.cup_" + ("benched" if xi.regulars_benched else "all_start"),
        rotation_params={"competition": CUP, "stage": stage, "opponent": name, "venue": venue, "days": days,
                         "benched": len(xi.regulars_benched)})


# --- head-to-head ------------------------------------------------------------------------------------------

def h2h_count(meetings: list[dict], home_club: str) -> PrematchH2HCount:
    pts = [result(*mine(r["score"], r, home_club)) for r in meetings]
    return PrematchH2HCount(played=len(pts), home_w=pts.count("W"), d=pts.count("D"), away_w=pts.count("L"))


def head_to_head(season: dict, results: list[dict], home: str, away: str) -> PrematchHeadToHead:
    """The meetings `with_seed_season` counts (the two seasons before, and this one's so far)."""
    meetings = sorted((r for r in [*season["past_meetings"], *results] if {r["home"], r["away"]} == {home, away}),
                      key=lambda r: (r["season"], r["matchday"]))
    return PrematchHeadToHead(
        all=h2h_count(meetings, home), at_this_ground=h2h_count([r for r in meetings if r["home"] == home], home),
        meetings=[PrematchMeeting(season=r["season"], matchday=r["matchday"], venue_club=r["home"], home_club=r["home"],
                                  away_club=r["away"], ft=(r["score"][0], r["score"][1]), ht=ht_score(r))
                  for r in meetings])


# --- the matchup -----------------------------------------------------------------------------------------

LEFT, RIGHT = ("LB", "LWB", "LM", "LW"), ("RB", "RWB", "RM", "RW")
MIDFIELD, FORWARDS, CENTRE_BACKS = ("DM", "CM", "AM"), ("ST",), ("CB",)
# zone: (home roles, away roles); the away side's right flank faces the home side's left
ZONES = {"home_wide_left": (LEFT, RIGHT), "home_wide_right": (RIGHT, LEFT), "midfield": (MIDFIELD, MIDFIELD),
         "home_attack": (FORWARDS, CENTRE_BACKS), "away_attack": (CENTRE_BACKS, FORWARDS)}


def _slots(team: Team, roles: tuple[str, ...]) -> tuple[list[str], list[str]]:
    slots = sorted((s for s in team.sheet.starters if s.role in roles), key=lambda s: s.slot)
    return [s.role for s in slots], [s.player_id for s in slots]


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _of(name: str) -> str:
    """The possessive: Harbour City's, Northgate Rovers'."""
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def line(zone: str, match: Match, side: Side) -> PrematchLine:
    """Who faces whom in one zone, said for `side`."""
    home_roles, home_ids = _slots(match.home, ZONES[zone][0])
    away_roles, away_ids = _slots(match.away, ZONES[zone][1])
    me, them = (match.home, match.away) if side == "home" else (match.away, match.home)
    my_roles, their_roles = (home_roles, away_roles) if side == "home" else (away_roles, home_roles)
    n, m = len(my_roles), len(their_roles)
    params: Params = {"team": me.name, "other": them.name, "mine": " ".join(my_roles) or "-",
                      "theirs": " ".join(their_roles) or "-", "n": n, "m": m}
    if zone == "midfield":
        how = "more" if n > m else "fewer" if n < m else "even"
        note = {"more": f"{me.name} have the extra man in midfield, {n} v {m}",
                "fewer": f"{me.name} are a man short in midfield, {n} v {m}",
                "even": f"{n} v {m} in midfield"}[how]
        key = f"prematch.line.midfield_{how}"
    elif zone in ("home_attack", "away_attack"):
        ours = (zone == "home_attack") == (side == "home")
        a, b = (me, them) if ours else (them, me)
        forwards, centre_backs = (n, m) if ours else (m, n)
        params.update(forwards=forwards, centre_backs=centre_backs)
        note = f"{_of(a.name)} {_plural(forwards, 'forward')} against {_of(b.name)} {_plural(centre_backs, 'centre-back')}"
        key = "prematch.line.our_attack" if ours else "prematch.line.their_attack"
    else:
        flank = ("left" if zone == "home_wide_left" else "right") if side == "home" else \
                ("right" if zone == "home_wide_left" else "left")
        params["flank"] = flank
        note = f"{_of(me.name)} {flank} flank: {params['mine']} against {params['theirs']}, {n} v {m}"
        key = "prematch.line.flank"
    return PrematchLine(zone=zone, home=home_roles, away=away_roles, home_players=home_ids, away_players=away_ids,
                        note=note, note_key=key, params=params)


ORDERED = {"line_height": (("low", "mid", "high"), "hold a higher line", "sit deeper"),
           "press": (("low", "mid", "high"), "press higher", "press less"),
           "width": (("narrow", "normal", "wide"), "play wider", "play narrower"),
           "tempo": (("slow", "normal", "fast"), "play faster", "play slower"),
           "passing": (("short", "mixed", "direct"), "go more direct", "keep the passing shorter")}
SWITCHES = {"counter_attack": "break quickly when they win the ball", "offside_trap": "play an offside trap",
            "time_wasting": "slow the game down when ahead"}
FOCUS = {"left": "down the left", "right": "down the right", "centre": "through the middle",
         "balanced": "on both flanks"}


def tactics_diff(match: Match, side: Side) -> list[PrematchTacticsDiff]:
    """Each tactic the two coaches set differently, said for `side`."""
    h, a = match.home.tactics, match.away.tactics
    me, them = (match.home.name, match.away.name) if side == "home" else (match.away.name, match.home.name)
    out = []
    for field in (*ORDERED, "attack_focus", *SWITCHES):
        hv, av = getattr(h, field), getattr(a, field)
        if hv == av:
            continue
        mv, tv = (hv, av) if side == "home" else (av, hv)
        params: Params = {"team": me, "other": them, "mine": str(mv).lower(), "theirs": str(tv).lower()}
        if field in ORDERED:
            order, up, down = ORDERED[field]
            more = order.index(mv) > order.index(tv)
            note = f"{me} {up if more else down} than {them} ({mv} v {tv})"
            key = f"prematch.tactics.{field}_{'more' if more else 'less'}"
        elif field == "attack_focus":
            note, key = f"{me} attack mostly {FOCUS[mv]}, {them} {FOCUS[tv]}", "prematch.tactics.attack_focus"
        else:
            who, other = (me, them) if mv else (them, me)
            note = f"{who} {SWITCHES[field]}; {other} do not"
            key = f"prematch.tactics.{field}_{'mine' if mv else 'theirs'}"
        out.append(PrematchTacticsDiff(field=field, home=str(hv).lower(), away=str(av).lower(), note=note,
                                       note_key=key, params=params))
    return out


# --- the report --------------------------------------------------------------------------------------------

def prematch(match: Match, season: dict, side: Side = "home") -> PrematchReport | None:
    """The whole report, or None for a match that is not one of the season's."""
    matchday = matchday_of(match)
    if matchday is None:
        return None
    results = before(season, matchday)
    standings = {row["club_id"]: row["position"] for row in table(results)}
    teams, taken = {}, ()
    for s, team in (("home", match.home), ("away", match.away)):
        club = team.club_id
        played = [r for r in results if club in (r["home"], r["away"])]
        games = [game(r, club) for r in played]
        xi = usual_xi(team, played[-LAST:])
        league = next_league(club, matchday, xi)
        cup = cup_tie(match, s, matchday, xi, taken)
        taken = (cup.opponent_id,) if cup else ()
        teams[s] = PrematchTeam(
            club_id=club, name=team.name, overall=record(games, standings.get(club)),
            home_only=record([g for g in games if g.venue == "H"]), away_only=record([g for g in games if g.venue == "A"]),
            last5=games[-LAST:][::-1], last5_stats=form_stats(played[-LAST:], club),
            next_fixture=cup or league, next_league=league, usual_xi_today=xi)
    return PrematchReport(
        match_id=match.match_id, season=SEASON, matchday=matchday, about=ABOUT, about_key="prematch.about",
        teams=teams, head_to_head=head_to_head(season, results, match.home.club_id, match.away.club_id),
        matchup=PrematchMatchup(perspective=side, home_formation=match.home.sheet.formation,
                                away_formation=match.away.sheet.formation,
                                lines=[line(z, match, side) for z in ZONES], tactics_diff=tactics_diff(match, side)))


@router.get("/matches/{match_id}/prematch", response_model=PrematchReport)
async def get_prematch(match_id: str, request: Request,
                       team: Side = Query("home", description="the side the matchup notes speak for")) -> PrematchReport:
    match = await request.app.state.adapters.matches.get_match(match_id)
    if match is None:
        raise HTTPException(404, f"match {match_id!r} not found")
    season = sims._season()
    report = None if season is None else prematch(match, season, team)
    if report is None:
        raise HTTPException(404, f"match {match_id!r} is not a game of the season, so it has no pre-match numbers")
    return report


__all__ = ["CONTRACT_MODELS", "PrematchReport", "matchday_of", "prematch", "router"]
