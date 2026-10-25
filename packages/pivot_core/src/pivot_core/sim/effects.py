"""Context effects (B14, first half): the pre-match background turned into small, explicit modifiers.

`context_effects(match)` reads the match's context and both squads and returns the list of
`ContextEffect`s that CTX-001 says the simulator plays by. It is a pure function: the same match
gives the same list, and nothing is drawn at random. Sizes follow CTX-002:

- former club: a player facing a club they left is more motivated, more so if they were released
  or hardly played there, left on bad terms, or play the game away;
- relationships: team-mates who played together before, did not fall out and play positions that
  link up pass better to each other (chemistry);
  a rival or feud on the other side means more fouls and cards;
- competition: big-match players keep their composure better in important games;
- stakes: a title race, relegation fight or knockout tie lifts both sides; players who do not
  handle pressure lose a little composure;
- crowd: the home side is lifted, away players lose a little composure, by how full the ground is
  (attendance over the venue's capacity in the fictional world);
- off-field news in the last 72 hours: a night out or late return makes legs go sooner, criticism
  or a contract dispute costs concentration;
- form: a player's last five ratings; fatigue: fewer than four days since the last game;
- weather: rain, wind, snow or a heavy pitch make ground passes less reliable for everyone.

Rules from CTX-001 and QA-012: one effect stays within +/-0.15, the effects on one person and one
target add up to at most +/-0.25 (team-wide effects count for every player of that side), and
every effect names the news item, career stint or relationship it comes from where there is one.

Applying the effects while the match is played is the second half of B14 and waits for B12.
"""

from __future__ import annotations

import math
from collections import defaultdict

from ..domain import ContextEffect, Match, Player, Team
from .world import CLUBS

MAX_EFFECT = 0.15
MAX_TOTAL = 0.25                     # one person, one target (CTX-001)
VENUE_CAPACITY = {c.venue: c.capacity for c in CLUBS}
CROWD_FULL = 50_000                  # counts as a full ground at a venue the fictional world does not know
NEWS_HOURS = 72
STAKES_LIFT = {"knockout": 0.04, "relegation": 0.04, "title_race": 0.03, "qualification": 0.02}
STAKES_NAME = {"knockout": "a knockout tie", "relegation": "a relegation fight",
               "title_race": "a title race", "qualification": "a race for a continental place"}
WEATHER_PASSING = {"rain": -0.03, "wind": -0.02, "snow": -0.04}
HEAVY_PITCH = -0.05
LOW_APPS_PER_SEASON = 10             # fewer league games a season than this counts as hardly playing
# Story first: D13's template cites the first effect about the person in a turning point.
ORDER = ("former_club", "rivalry", "off_field", "fatigue", "former_teammate", "form", "stakes", "crowd",
         "competition", "weather")


def context_effects(match: Match) -> list[ContextEffect]:
    """Every effect the context gives this match, story effects first."""
    ctx = match.context
    teams = (match.home, match.away)
    side_of = {p.player_id: t.side for t in teams for p in t.squad} | {t.coach.coach_id: t.side for t in teams}
    name = {p.player_id: p.name for t in teams for p in t.squad} | {t.coach.coach_id: t.coach.name for t in teams}
    role = {p.player_id: p.role for t in teams for p in t.squad}
    out: list[ContextEffect] = []

    def add(subject: str, source: str, target: str, delta: float, note: str, ref: str | None = None) -> None:
        delta = round(max(-MAX_EFFECT, min(MAX_EFFECT, delta)), 3)
        if delta:                                         # rounds to nothing: no effect to record
            key = f"fx-{subject}-{source}-{target}" + (f"-{ref}" if ref else "")
            out.append(ContextEffect(effect_id=key, subject_id=subject, source=source, source_ref=ref,
                                     target=target, delta=delta, note=note[:120]))

    for team, opponent in ((match.home, match.away), (match.away, match.home)):
        for p in team.squad:
            _former_club(add, p, team, opponent)

    for r in ctx.relationships:
        mine, theirs = side_of.get(r.person_id), side_of.get(r.other_id)
        if mine is None or theirs is None:
            continue
        if r.kind in ("rival", "feud") or r.sentiment < 0:
            if mine != theirs:
                for who, other in ((r.person_id, r.other_id), (r.other_id, r.person_id)):
                    note = f"bad blood with {name[other]} on the other side"
                    add(who, "rivalry", "aggression", 0.05, note, r.relationship_id)
                    add(who, "rivalry", "card_risk", 0.05, note, r.relationship_id)
        elif (r.kind == "former_teammate" and mine == theirs and r.sentiment > 0
              and r.person_id in role and r.other_id in role and can_combine(role[r.person_id], role[r.other_id])):
            chem = min(0.01 * r.shared_seasons, 0.05)
            for who, other in ((r.person_id, r.other_id), (r.other_id, r.person_id)):
                add(who, "former_teammate", "chemistry", chem, f"played together before with {name[other]}",
                    r.relationship_id)

    for n in ctx.news:
        if n.sentiment != "negative" or n.hours_before_kickoff > NEWS_HOURS or n.subject_id not in side_of:
            continue
        person = _person(teams, n.subject_id)
        if n.kind in ("nightlife", "late_return"):
            pro = person.personality.professionalism if person else 50
            add(n.subject_id, "off_field", "stamina_decay", 0.03 * n.severity * (1 - pro / 100),
                "a late night before the game: legs may go sooner", n.news_id)
            add(n.subject_id, "off_field", "concentration", -0.01 * n.severity,
                "a late night before the game", n.news_id)
        elif n.kind in ("contract_dispute", "public_criticism"):
            add(n.subject_id, "off_field", "concentration", {1: -0.01, 2: -0.025, 3: -0.04}[n.severity],
                "distracted by " + ("a contract dispute" if n.kind == "contract_dispute" else "public criticism"),
                n.news_id)

    for c in ctx.conditions:
        if c.player_id not in side_of:
            continue
        if c.recent_ratings:
            avg = sum(c.recent_ratings) / len(c.recent_ratings)
            add(c.player_id, "form", "motivation", (avg - 6.7) * 0.03,
                f"average rating {avg:.1f} over the last {len(c.recent_ratings)} games")
        if c.days_since_last_match is not None and c.days_since_last_match < 4:
            add(c.player_id, "fatigue", "injury_risk", 0.15,
                f"{c.days_since_last_match} days since the last game")

    if ctx.stakes in STAKES_LIFT:
        for team in teams:
            add(team.side, "stakes", "motivation", STAKES_LIFT[ctx.stakes], f"{STAKES_NAME[ctx.stakes]} lifts the side")
            for p in team.squad:
                if p.personality.pressure < 40:
                    add(p.player_id, "stakes", "composure", -0.02,
                        f"pressure rating {p.personality.pressure} in {STAKES_NAME[ctx.stakes]}")

    if not ctx.competition.neutral_venue and ctx.attendance:
        capacity = VENUE_CAPACITY.get(ctx.venue, CROWD_FULL)
        full = min(ctx.attendance / capacity, 1.0)
        crowd = f"crowd of {ctx.attendance:,} in a ground for {capacity:,}"
        add(match.home.side, "crowd", "motivation", 0.04 * full, f"home {crowd}")
        for p in match.away.squad:
            add(p.player_id, "crowd", "composure", -0.02 * full * (1 - p.personality.pressure / 100),
                f"away {crowd}, pressure rating {p.personality.pressure}")

    importance = ctx.competition.importance
    for team in teams:
        for p in team.squad:
            big = p.personality.big_matches
            add(p.player_id, "competition", "composure", (big - 50) / 50 * 0.02 * (importance - 1),
                f"big-match rating {big}, match importance {importance} of 5")

    passing = WEATHER_PASSING.get(ctx.weather, 0.0) + (HEAVY_PITCH if ctx.pitch == "heavy" else 0.0)
    if passing:
        for team in teams:
            add(team.side, "weather", "chemistry", max(passing, -0.05),
                f"{ctx.weather} weather, {ctx.pitch} pitch: ground passes less reliable")

    out = _cap(out, side_of)
    return sorted(out, key=lambda e: (ORDER.index(e.source), e.subject_id, e.target))


LINE = {"GK": "GK", "CB": "CB", "LB": "LB", "LWB": "LB", "RB": "RB", "RWB": "RB", "DM": "DM", "CM": "CM",
        "AM": "AM", "LM": "LW", "LW": "LW", "RM": "RW", "RW": "RW", "ST": "ST"}
# Positions that pass to each other on the pitch: the keeper and the centre-backs, a full-back and the
# winger ahead on the same flank, neighbours through the middle, and the forwards with whoever feeds them.
PARTNERS = {
    "GK": {"CB"},
    "CB": {"GK", "CB", "LB", "RB", "DM"},
    "LB": {"CB", "DM", "CM", "LW"},
    "RB": {"CB", "DM", "CM", "RW"},
    "DM": {"CB", "LB", "RB", "DM", "CM", "AM"},
    "CM": {"LB", "RB", "DM", "CM", "AM", "LW", "RW", "ST"},
    "AM": {"DM", "CM", "AM", "LW", "RW", "ST"},
    "LW": {"LB", "CM", "AM", "ST"},
    "RW": {"RB", "CM", "AM", "ST"},
    "ST": {"CM", "AM", "LW", "RW", "ST"},
}


def can_combine(role_a: str, role_b: str) -> bool:
    """True when the two positions link up in play, so playing together before can matter (CTX-006)."""
    return LINE[role_b] in PARTNERS[LINE[role_a]]


def with_effects(match: Match) -> Match:
    """The match with `context.effects` filled; nothing else changes."""
    return match.model_copy(update={"context": match.context.model_copy(update={"effects": context_effects(match)})})


def _person(teams: tuple[Team, Team], person_id: str) -> Player | None:
    return next((p for t in teams for p in t.squad if p.player_id == person_id), None)


def _former_club(add, p: Player, team: Team, opponent: Team) -> None:
    """CTX-002 former club: +0.03, +0.03 released or hardly played, +0.02 bad terms, +0.01 away, at most 0.10."""
    for s in p.career:
        if s.club_id != opponent.club_id or s.to_year is None or s.as_coach:
            continue
        seasons = max(s.to_year - s.from_year, 1)
        cast_off = s.departure == "released" or s.appearances / seasons < LOW_APPS_PER_SEASON
        sour = s.departure_mood == "acrimonious"
        delta = 0.03 + 0.03 * cast_off + 0.02 * sour + 0.01 * (team.side == "away")
        where = "away at" if team.side == "away" else "at home to"
        how = ("released by them" if s.departure == "released" else "left on bad terms" if sour
               else "hardly played there" if cast_off else "left on good terms")
        add(p.player_id, "former_club", "motivation", min(delta, 0.10),
            f"{where} former club {s.club_name}, {how}", s.stint_id)


def _cap(effects: list[ContextEffect], side_of: dict[str, str]) -> list[ContextEffect]:
    """Scale one person's own effects on a target down so that, with their side's team-wide effects,
    they add up to at most MAX_TOTAL either way (CTX-001, QA-012)."""
    team_wide = defaultdict(float)
    for e in effects:
        if e.subject_id in ("home", "away"):
            team_wide[e.subject_id, e.target] += e.delta
    own = defaultdict(list)
    for e in effects:
        if e.subject_id not in ("home", "away"):
            own[e.subject_id, e.target].append(e)
    scaled = {}
    for (person, target), es in own.items():
        shared = team_wide[side_of.get(person), target]       # at most stakes + crowd, well inside the cap
        mine = sum(e.delta for e in es)
        total = shared + mine
        if abs(total) <= MAX_TOTAL:
            continue
        k = (math.copysign(MAX_TOTAL, total) - shared) / mine
        for e in es:
            scaled[e.effect_id] = math.trunc(e.delta * k * 1000) / 1000   # towards zero, so the sum stays inside
    return [e.model_copy(update={"delta": scaled[e.effect_id]}) if e.effect_id in scaled else e for e in effects]
