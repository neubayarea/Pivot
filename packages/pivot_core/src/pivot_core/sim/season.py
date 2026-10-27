"""The season so far (B13) and the off-field stories it gives the demo match.

`play(fixture)` simulates one league match of the fictional world and keeps only what the stories
need: the score, who scored, red cards, substitutions and each player's rating. scripts/make_season.py plays matchdays
1-29, plus the four meetings of the two clubs in the two seasons before, and keeps them in
eval/fixtures/season-2026.json. `with_season(match, season)` fills the demo match's careers and
context from that file:

- form, table position, head-to-head and stakes are counted from the results;
- news is derived from them (top scorers, a coach under pressure, leads thrown away);
- three stories are placed by hand on the demo's turning points (see `_DEMO_CAREERS` and
  `_demo_news`): the 38' red card, the 63' substitution and the 85' substitution.

`with_seed_season(match, season)` does the same for the site's seed matches (Bx13): each one is
played as a matchday drawn from its seed, so form, table and head-to-head differ from match to
match, and three stories are drawn instead of placed: an away starter who once played for Harbour
City, a home player one game short of a round number of appearances, and one more headline.

None of this changes how the match is played. `sim/effects.py` (B14) turns this context into the
match's context effects; the engine plays by them only with the B14 switch on (CTX-007).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import numpy as np

from ..analytics import StatCalculator, player_match_stats
from ..domain import (
    CareerStint, HeadToHead, Match, OffFieldEvent, PastMeeting, PreMatchCondition, Relationship, Team, TeamForm,
)
from ..domain.common import PITCH_LENGTH, PITCH_WIDTH
from .effects import can_combine, with_effects
from .engine import simulate
from .world import BY_ID, CLUB_NAMES, DEMO_MATCHDAY, HBC, ROV, SEASON, Fixture, fixture_match, with_careers

SEASON_FILE = "season-2026.json"


def play(fx: Fixture) -> dict:
    """One simulated league match, reduced to its result. Players are kept as (club, shirt)."""
    match = fixture_match(fx)
    out = simulate(match)
    shirt = {p.player_id: p.shirt_number for t in (match.home, match.away) for p in t.squad}
    club = {"home": fx.home, "away": fx.away}

    def who(e: dict, pid: str | None = None) -> list:
        return [club[e["team"]], shirt[pid or e["player_id"]], e["t"] // 60]

    events = out.events
    team_of = {p.player_id: p.team for t in (match.home, match.away) for p in t.squad}
    return {
        "season": fx.season, "matchday": fx.matchday, "home": fx.home, "away": fx.away, "seed": fx.seed,
        "score": [out.match.score.home, out.match.score.away],
        "goals": [who(e) for e in events if e["type"] == "shot" and e.get("shot_outcome") == "goal"],
        "reds": [who(e) for e in events
                 if e["type"] == "card" and (e.get("foul") or {}).get("card") in ("red", "second_yellow")],
        "subs_on": [who(e, e["substitution"]["player_on_id"]) for e in events if e["type"] == "substitution"],
        # (club, shirt, rating) for everyone who played: the form going into the demo (CTX-002 form)
        "ratings": [[club[team_of[s.player_id]], shirt[s.player_id], s.rating]
                    for s in player_match_stats(StatCalculator.from_sim(_on_pitch(out)))],
    }


def _on_pitch(out):
    """The output with positions clipped to the pitch. A rare frame puts an interception 0.4 m over the
    touchline (handed to B12), which the frame format refuses; ratings do not depend on it."""
    lo, hi = np.zeros(2), np.array([PITCH_LENGTH, PITCH_WIDTH])
    ball = out.frames_ball.copy()
    ball[:, :2] = np.clip(ball[:, :2], lo, hi)
    return replace(out, frames_pos=np.clip(out.frames_pos, lo, hi), frames_ball=ball)


def load_season(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / SEASON_FILE).read_text(encoding="utf-8"))


# --- counted from the results ----------------------------------------------------------------------

def _points(r: dict, club: str) -> tuple[int, int, int]:
    """(points, goals for, goals against) for one club in one result."""
    gf, ga = r["score"] if r["home"] == club else r["score"][::-1]
    return (3 if gf > ga else 1 if gf == ga else 0), gf, ga


def table(results: list[dict]) -> list[dict]:
    """League table: points, then goal difference, then goals scored."""
    rows = {c: {"club_id": c, "played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "points": 0}
            for c in BY_ID}
    for r in results:
        for club in (r["home"], r["away"]):
            pts, gf, ga = _points(r, club)
            row = rows[club]
            row["played"] += 1
            row[{3: "won", 1: "drawn", 0: "lost"}[pts]] += 1
            row["gf"] += gf
            row["ga"] += ga
            row["points"] += pts
    ranked = sorted(rows.values(), key=lambda x: (-x["points"], -(x["gf"] - x["ga"]), -x["gf"], x["club_id"]))
    for pos, row in enumerate(ranked, start=1):
        row["position"] = pos
    return ranked


def form(results: list[dict], club: str, side: str, standings: list[dict]) -> TeamForm:
    games = sorted((r for r in results if club in (r["home"], r["away"])), key=lambda r: r["matchday"])[-5:]
    rows = [_points(r, club) for r in games]
    row = next(x for x in standings if x["club_id"] == club)
    return TeamForm(side=side, last_results=[{3: "W", 1: "D", 0: "L"}[p] for p, _, _ in rows],
                    goals_for_last5=sum(gf for _, gf, _ in rows), goals_against_last5=sum(ga for _, _, ga in rows),
                    league_position=row["position"], points=row["points"])


def stakes(standings: list[dict], clubs: tuple[str, str]) -> str:
    """What the match is about for either side (Pivot rule, CTX-005): title race if a side is in the
    top two or within six points of first; relegation if in the bottom three or within three points
    of it; qualification if in the top six. The bigger stake wins."""
    first = standings[0]["points"]
    drop = standings[-3]["points"]           # 18th place, the first relegation spot
    found = set()
    for row in standings:
        if row["club_id"] not in clubs:
            continue
        if row["position"] <= 2 or first - row["points"] <= 6:
            found.add("title_race")
        elif row["position"] >= len(standings) - 2 or row["points"] - drop <= 3:
            found.add("relegation")
        elif row["position"] <= 6:
            found.add("qualification")
    return next((s for s in ("title_race", "relegation", "qualification") if s in found), "none")


def head_to_head(meetings: list[dict], home_club: str) -> HeadToHead:
    """Meetings of the two demo clubs, newest last, counted from the demo's home side."""
    meetings = sorted(meetings, key=lambda r: (r["season"], r["matchday"]))
    pts = [_points(r, home_club)[0] for r in meetings]
    return HeadToHead(
        played=len(meetings), home_wins=pts.count(3), draws=pts.count(1), away_wins=pts.count(0),
        last_meetings=[PastMeeting(season=str(r["season"]), home_club_id=r["home"], away_club_id=r["away"],
                                   home_goals=r["score"][0], away_goals=r["score"][1], competition_id="fl-1")
                       for r in meetings][-10:])


def season_stats(results: list[dict]) -> dict[tuple[str, int], dict[str, int]]:
    """League appearances and goals per (club, shirt). The starters are shirts 1-11 in every match."""
    stats: dict[tuple[str, int], dict[str, int]] = defaultdict(lambda: {"apps": 0, "goals": 0})
    for r in results:
        for club in (r["home"], r["away"]):
            for shirt in range(1, 12):
                stats[club, shirt]["apps"] += 1
        for club, shirt, _ in r["subs_on"]:
            stats[club, shirt]["apps"] += 1
        for club, shirt, _ in r["goals"]:
            stats[club, shirt]["goals"] += 1
    return stats


def leads_lost(results: list[dict], club: str) -> tuple[int, int]:
    """(games, points) the club dropped after being ahead."""
    games = points = 0
    for r in results:
        if club not in (r["home"], r["away"]):
            continue
        diff, led = 0, False
        for scorer_club, _, _ in sorted(r["goals"], key=lambda g: g[2]):
            diff += 1 if scorer_club == club else -1
            led |= diff > 0
        pts = _points(r, club)[0]
        if led and pts < 3:
            games, points = games + 1, points + 3 - pts
    return games, points


# --- careers and ties --------------------------------------------------------------------------------

def _stint(pid: str, k: int, club: str, frm: int, to: int | None, apps: int, goals: int = 0,
           departure: str | None = None, mood: str = "neutral") -> CareerStint:
    return CareerStint(stint_id=f"{pid}-c{k}", club_id=club, club_name=CLUB_NAMES[club], from_year=frm, to_year=to,
                       appearances=apps, goals=goals, departure=departure, departure_mood=mood)


# Hand-placed on the demo's turning points. The current club's appearances and goals are those of
# the seasons before this one; this season's are added from the results.
_DEMO_CAREERS: dict[str, list[CareerStint]] = {
    # 38' red card: Rovers centre-back N. Torenini came through Harbour City and left on bad terms.
    "a04": [_stint("a04", 1, HBC.club_id, 2019, 2024, 71, 2, "transfer", "acrimonious"),
            _stint("a04", 2, ROV.club_id, 2024, None, 58, 1)],
    # 85' substitution: Harbour City centre-back A. Tesvikkaer spent seven seasons at Rovers.
    "h13": [_stint("h13", 1, "club-x-fen", 2013, 2016, 74, 3, "transfer"),
            _stint("h13", 2, ROV.club_id, 2016, 2023, 186, 9, "contract_end", "amicable"),
            _stint("h13", 3, HBC.club_id, 2023, None, 61, 2)],
    # 63' substitution: holding midfielder P. Milier comes on for his 100th Harbour City game.
    "h15": [_stint("h15", 1, "club-x-kir", 2018, 2022, 96, 4, "transfer"),
            _stint("h15", 2, HBC.club_id, 2022, None, 0)],
}
_HUNDREDTH = "h15"                            # his appearances are set to 99, whatever the season gave


def _story_team(team: Team, stats: dict, played: int, careers: dict[str, list[CareerStint]] = _DEMO_CAREERS,
                hundredth: str | None = _HUNDREDTH) -> Team:
    team = with_careers(team)
    squad = []
    for p in team.squad:
        career = list(careers.get(p.player_id, p.career))
        s = stats.get((team.club_id, p.shirt_number), {"apps": 0, "goals": 0})
        now = career[-1]
        apps = 99 if p.player_id == hundredth else now.appearances + s["apps"]
        career[-1] = now.model_copy(update={"appearances": apps, "goals": now.goals + s["goals"]})
        squad.append(p.model_copy(update={"career": career}))
    coach = team.coach.career[-1]
    coach_career = [*team.coach.career[:-1], coach.model_copy(update={"appearances": coach.appearances + played})]
    return team.model_copy(update={"squad": squad, "coach": team.coach.model_copy(update={"career": coach_career})})


def ties(home: Team, away: Team) -> list[Relationship]:
    """People on opposite sides who were at the same club for at least three seasons at the same time."""
    def people(team: Team):
        return [(p.player_id, p.career) for p in team.squad] + [(team.coach.coach_id, team.coach.career)]

    out = []
    for pid, mine in people(home):
        for oid, theirs in people(away):
            for s in mine:
                for t in theirs:
                    shared = min(s.to_year or SEASON, t.to_year or SEASON) - max(s.from_year, t.from_year)
                    if s.club_id != t.club_id or shared < 3 or (s.as_coach and t.as_coach):
                        continue
                    sour = "acrimonious" in (s.departure_mood, t.departure_mood)
                    person, other, kind = (pid, oid, "former_teammate")
                    if s.as_coach:                    # the away player's former coach
                        person, other, kind = oid, pid, "former_coach"
                    elif t.as_coach:
                        kind = "former_coach"
                    out.append(Relationship(relationship_id=f"rel-{person}-{other}", person_id=person, other_id=other,
                                            kind=kind, shared_seasons=shared, sentiment=0.0 if sour else 0.3))
    return sorted(out, key=lambda r: -r.shared_seasons)


def teammates(team: Team) -> list[Relationship]:
    """Players of one side who were team-mates at an earlier club, in positions that link up in play
    (CTX-006). Any overlap counts; chemistry grows with the seasons shared."""
    out = []
    squad = team.squad
    for n, a in enumerate(squad):
        for b in squad[n + 1:]:
            if not can_combine(a.role, b.role):
                continue
            best = None
            for s in a.career:
                for t in b.career:
                    if s.club_id != t.club_id or s.club_id == team.club_id or s.to_year is None or t.to_year is None:
                        continue
                    shared = min(s.to_year, t.to_year) - max(s.from_year, t.from_year)
                    if shared >= 1 and (best is None or shared > best[0]):
                        best = (shared, "acrimonious" in (s.departure_mood, t.departure_mood))
            if best:
                out.append(Relationship(relationship_id=f"rel-{a.player_id}-{b.player_id}", person_id=a.player_id,
                                        other_id=b.player_id, kind="former_teammate", shared_seasons=best[0],
                                        sentiment=0.0 if best[1] else 0.3))
    return sorted(out, key=lambda r: -r.shared_seasons)


def recent_form(team: Team, results: list[dict]) -> list[PreMatchCondition]:
    """Each player's last five league ratings before the demo, newest last (CTX-002 form)."""
    games = sorted((r for r in results if team.club_id in (r["home"], r["away"])), key=lambda r: r["matchday"])
    ratings: dict[int, list[float]] = defaultdict(list)
    for r in games:
        for club, shirt, rating in r.get("ratings", []):
            if club == team.club_id:
                ratings[shirt].append(rating)
    return [PreMatchCondition(player_id=p.player_id, recent_ratings=ratings[p.shirt_number][-5:])
            for p in team.squad if ratings.get(p.shirt_number)]


# --- news ----------------------------------------------------------------------------------------------

def _demo_news(home: Team, away: Team) -> list[OffFieldEvent]:
    name = {p.player_id: p.name for t in (home, away) for p in t.squad}
    return [
        OffFieldEvent(news_id="news-a04-return", subject_id="a04", kind="fan_conflict", hours_before_kickoff=20,
                      severity=2, sentiment="negative",
                      headline=f"Harbour City fans plan a hostile welcome for {name['a04']}, "
                               "who left the club for Rovers on bad terms in 2024"),
        OffFieldEvent(news_id="news-h15-100", subject_id="h15", kind="milestone", hours_before_kickoff=48,
                      sentiment="positive",
                      headline=f"{name['h15']} is one game away from 100 appearances for Harbour City"),
    ]


def derived_news(teams: list[Team], results: list[dict], stats: dict) -> list[OffFieldEvent]:
    """Headlines that follow from the season: a coach under pressure, leads thrown away, top scorers."""
    out = []
    for team in teams:
        club, coach = team.club_id, team.coach
        last = sorted((r for r in results if club in (r["home"], r["away"])), key=lambda r: r["matchday"])[-5:]
        losses = sum(_points(r, club)[0] == 0 for r in last)
        wins = sum(_points(r, club)[0] == 3 for r in last)
        games, points = leads_lost(results, club)
        if losses >= 3:
            out.append(OffFieldEvent(news_id=f"news-{coach.coach_id}-form", subject_id=coach.coach_id,
                                     kind="public_criticism", hours_before_kickoff=36, severity=2, sentiment="negative",
                                     headline=f"{coach.name} under pressure after {losses} defeats in "
                                              f"{team.name}{"'" if team.name.endswith("s") else "'s"} last five league games"))
        elif games >= 3:
            out.append(OffFieldEvent(news_id=f"news-{coach.coach_id}-leads", subject_id=coach.coach_id,
                                     kind="public_criticism", hours_before_kickoff=36, sentiment="negative",
                                     headline=f"{coach.name} criticised after {team.name} dropped {points} points "
                                              f"from winning positions this season"))
        elif wins >= 4:
            out.append(OffFieldEvent(news_id=f"news-{coach.coach_id}-form", subject_id=coach.coach_id,
                                     kind="milestone", hours_before_kickoff=36, sentiment="positive",
                                     headline=f"{coach.name}'s {team.name} have won {wins} of their last five"))
    for team in teams:
        best = max(team.squad, key=lambda p: (stats.get((team.club_id, p.shirt_number), {}).get("goals", 0),
                                              -p.shirt_number))
        goals = stats.get((team.club_id, best.shirt_number), {}).get("goals", 0)
        if goals >= 5:
            out.append(OffFieldEvent(news_id=f"news-{best.player_id}-goals", subject_id=best.player_id,
                                     kind="milestone", hours_before_kickoff=72, sentiment="positive",
                                     headline=f"{best.name} has {goals} league goals this season, "
                                              f"the most at {team.name}"))
    return out


def _before(season: dict, matchday: int) -> list[dict]:
    return [r for r in season["results"] if r["season"] == SEASON and r["matchday"] < matchday]


def _with_context(match: Match, season: dict, results: list[dict], stats: dict, home: Team, away: Team,
                  stories: list[OffFieldEvent]) -> Match:
    """The match with these squads and the context counted from the results before it."""
    standings = table(results)
    clubs = (home.club_id, away.club_id)
    meetings = [r for r in [*season["past_meetings"], *results] if {r["home"], r["away"]} == set(clubs)]
    news = (stories + derived_news([home, away], results, stats))[:5]
    context = match.context.model_copy(update={
        "stakes": stakes(standings, clubs),
        "form": [form(results, home.club_id, "home", standings), form(results, away.club_id, "away", standings)],
        "head_to_head": head_to_head(meetings, home.club_id),
        "news": news,
        "relationships": ties(home, away) + teammates(home) + teammates(away),
        "conditions": recent_form(home, results) + recent_form(away, results),
    })
    return match.model_copy(update={"home": home, "away": away, "context": context})


def with_season(match: Match, season: dict) -> Match:
    """The demo match with its careers and pre-match context filled from the season so far."""
    assert (match.home.club_id, match.away.club_id) == (HBC.club_id, ROV.club_id), "only the demo fixture"
    results = _before(season, DEMO_MATCHDAY)
    stats = season_stats(results)
    played = DEMO_MATCHDAY - 1
    home, away = _story_team(match.home, stats, played), _story_team(match.away, stats, played)
    return _with_context(match, season, results, stats, home, away, _demo_news(home, away))


# --- the site's seed matches (Bx13) -------------------------------------------------------------------

FIRST_SEED_MATCHDAY = 8                       # five games of form, and a table that means something
MILESTONE_STEP = 50                           # appearances: 50, 100, 150, ...
_RETURN_MOODS = (("acrimonious", "neutral", "amicable"), (0.4, 0.3, 0.3))


def with_seed_season(match: Match, season: dict) -> Match:
    """A seed match (Harbour City v Northgate Rovers with the seed's squads) with careers, pre-match
    context and context effects, as a matchday of the season drawn from the seed. The same seed gives
    the same context every time; nothing here changes how the match is played."""
    assert (match.home.club_id, match.away.club_id) == (HBC.club_id, ROV.club_id), "a seed match"
    rng = np.random.default_rng([match.seed or 0, 14])
    matchday = int(rng.integers(FIRST_SEED_MATCHDAY, DEMO_MATCHDAY))
    results = _before(season, matchday)
    stats = season_stats(results)
    home, away = (_story_team(t, stats, matchday - 1, {}, None) for t in (match.home, match.away))
    away, back = _returner(rng, away, home)
    home, milestone = _milestone(home)
    stories = [n for n in (back, milestone, _headline(rng, home, away)) if n is not None]
    return with_effects(_with_context(match, season, results, stats, home, away, stories))


def _returner(rng: np.random.Generator, team: Team, opponent: Team) -> tuple[Team, OffFieldEvent | None]:
    """An outfield starter who played for the opponent before: the club before this one becomes theirs."""
    starters = {s.player_id for s in team.sheet.starters if s.role != "GK"}
    pool = [p for p in team.squad if p.player_id in starters and len(p.career) > 1]
    if not pool:
        return team, None
    p = pool[int(rng.integers(len(pool)))]
    moods, odds = _RETURN_MOODS
    mood = str(rng.choice(moods, p=odds))
    last = p.career[-2]
    stint = last.model_copy(update={"club_id": opponent.club_id, "club_name": CLUB_NAMES[opponent.club_id],
                                    "loan": False, "departure_mood": mood,
                                    "departure": "transfer" if last.loan else last.departure})
    player = p.model_copy(update={"career": [*p.career[:-2], stint, p.career[-1]]})
    team = team.model_copy(update={"squad": [player if q.player_id == p.player_id else q for q in team.squad]})
    if mood == "acrimonious":
        news = OffFieldEvent(news_id=f"news-{p.player_id}-return", subject_id=p.player_id, kind="fan_conflict",
                             hours_before_kickoff=20, severity=2, sentiment="negative",
                             headline=f"{opponent.name} fans plan a hostile welcome for {p.name}, "
                                      f"who left the club on bad terms in {stint.to_year}")
    else:
        news = OffFieldEvent(news_id=f"news-{p.player_id}-return", subject_id=p.player_id, kind="milestone",
                             hours_before_kickoff=30, sentiment="neutral",
                             headline=f"{p.name} faces {opponent.name} for the first time since leaving "
                                      f"the club in {stint.to_year}")
    return team, news


def _milestone(team: Team) -> tuple[Team, OffFieldEvent | None]:
    """The player nearest a round number of appearances for the club is one game short of it."""
    def target(p) -> int:
        return (p.career[-1].appearances // MILESTONE_STEP + 1) * MILESTONE_STEP

    pool = [p for p in team.squad if p.career[-1].appearances >= MILESTONE_STEP - 10]
    if not pool:
        return team, None
    p = min(pool, key=lambda q: (target(q) - q.career[-1].appearances, q.shirt_number))
    goal = target(p)
    now = p.career[-1].model_copy(update={"appearances": goal - 1})
    player = p.model_copy(update={"career": [*p.career[:-1], now]})
    team = team.model_copy(update={"squad": [player if q.player_id == p.player_id else q for q in team.squad]})
    return team, OffFieldEvent(news_id=f"news-{p.player_id}-{goal}", subject_id=p.player_id, kind="milestone",
                               hours_before_kickoff=48, sentiment="positive",
                               headline=f"{p.name} is one game away from {goal} appearances for {team.name}")


# kind, sentiment, severity, headline ({name}, {team}, {year})
_HEADLINES = (
    ("contract_dispute", "negative", 1, "{name} and {team} are still apart on a new contract"),
    ("transfer_rumour", "neutral", 1, "{name} is linked with a move away from {team} in the winter window"),
    ("new_contract", "positive", 1, "{name} signs a new contract with {team} until {year}"),
    ("nightlife", "negative", 1, "{name} of {team} was seen at a nightclub two nights before the game"),
)


def _headline(rng: np.random.Generator, home: Team, away: Team) -> OffFieldEvent | None:
    """One more headline about a starter of either side, in about two matches out of three."""
    if rng.random() >= 0.65:
        return None
    team = (home, away)[int(rng.integers(2))]
    slot = team.sheet.starters[int(rng.integers(len(team.sheet.starters)))]
    p = next(q for q in team.squad if q.player_id == slot.player_id)
    kind, sentiment, severity, text = _HEADLINES[int(rng.integers(len(_HEADLINES)))]
    return OffFieldEvent(news_id=f"news-{p.player_id}-{kind}", subject_id=p.player_id, kind=kind,
                         hours_before_kickoff=int(rng.integers(30, 61)), severity=severity, sentiment=sentiment,
                         headline=text.format(name=p.name, team=team.name, year=SEASON + 3))
