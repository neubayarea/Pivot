"""A fictional league (B13): twenty clubs with squads, coaches and careers, and a season schedule.

Everything comes from one seed, so the world is the same on every machine. Harbour City and
Northgate Rovers are built exactly as the demo match builds them (the demo seed), so the demo is one
fixture of this season: matchday 30, Harbour City at home. All names are fictional.

The season itself (scores, scorers, red cards, substitutions) is simulated once by
scripts/make_season.py and kept in eval/fixtures/season-2026.json; `season.py` turns it into the
demo match's form, table, head-to-head, stakes and news.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import numpy as np

from ..domain import CareerStint, Coach, Competition, Match, MatchContext, Player, Referee, Team
from .presets import DEMO_1021
from .squads import _name, build_team

WORLD_SEED = 2026
SEASON = 2026                                 # a calendar-year season, March to November
DEMO_MATCHDAY = 30                            # 21 October: Harbour City v Northgate Rovers
COMPETITION = Competition(competition_id="fl-1", name="Freeland League", level="league", importance=2)


@dataclass(frozen=True)
class Club:
    club_id: str
    name: str
    short: str
    color: str
    venue: str
    capacity: int
    strength: float
    formation: str


HBC = Club("club-hbc", "Harbour City", "HBC", "#1E6B45", "Harbour Park", 42000,
           DEMO_1021.home_strength, DEMO_1021.home_formation)
ROV = Club("club-rov", "Northgate Rovers", "ROV", "#4A1D57", "Northgate Lane", 31000,
           DEMO_1021.away_strength, DEMO_1021.away_formation)

CLUBS: tuple[Club, ...] = (
    HBC, ROV,
    Club("club-cor", "Corvale City", "COR", "#B22234", "The Corvale Bowl", 52000, 75, "4-3-3"),
    Club("club-tes", "Tessmouth United", "TES", "#1C3F94", "Quayside Park", 47000, 74, "4-2-3-1"),
    Club("club-elm", "Elmshaw Athletic", "ELM", "#D4A017", "Elmshaw Road", 36000, 73, "4-4-2"),
    Club("club-van", "Vantry Town", "VAN", "#0F7C8C", "Vantry Common", 28000, 71, "4-1-4-1"),
    Club("club-dun", "Dunmere FC", "DUN", "#6B2D2D", "Mere Street", 30000, 71, "4-3-3"),
    Club("club-kel", "Kelvar Wanderers", "KEL", "#E87722", "Kelvar Meadow", 26000, 70, "4-2-3-1"),
    Club("club-ost", "Ostrin Albion", "OST", "#2E8B57", "Albion Fields", 33000, 70, "3-5-2"),
    Club("club-fal", "Fallowden", "FAL", "#5B5EA6", "The Fallow", 22000, 69, "4-4-2"),
    Club("club-mar", "Marrick Vale", "MAR", "#8B0000", "Vale Park North", 24000, 69, "4-3-3"),
    Club("club-sal", "Saltreach Rangers", "SAL", "#00539C", "Saltreach Docks", 27000, 68, "4-2-3-1"),
    Club("club-pel", "Pellow Bay", "PEL", "#3CB4E5", "Bayfront Stadium", 21000, 68, "4-1-4-1"),
    Club("club-qua", "Quarrystone United", "QUA", "#7D7D7D", "The Quarry", 19000, 67, "5-4-1"),
    Club("club-bri", "Brightmoor", "BRI", "#F2C14E", "Moorside", 20000, 67, "4-4-2"),
    Club("club-hol", "Hollin Park", "HOL", "#4B6043", "Hollin Lane", 18000, 66, "4-3-3"),
    Club("club-wes", "Westerby Town", "WES", "#A23B72", "Westerby Ground", 17000, 66, "4-2-3-1"),
    Club("club-tho", "Thornwick Athletic", "THO", "#2F2F2F", "Thornwick Park", 16000, 65, "5-4-1"),
    Club("club-gre", "Greywater FC", "GRE", "#708090", "Greywater Mill", 15000, 65, "4-4-2"),
    Club("club-lun", "Lunsford Sporting", "LUN", "#C04000", "Lunsford Green", 14000, 64, "4-1-4-1"),
)
BY_ID = {c.club_id: c for c in CLUBS}

# Clubs outside the league that careers pass through: the second tier and two fictional countries.
OTHER_CLUBS: dict[str, str] = {
    "club-x-mos": "Mossgate", "club-x-kir": "Kirran Town", "club-x-ebb": "Ebberley",
    "club-x-sta": "Stannard United", "club-x-fen": "Fenrow", "club-x-ash": "Ashby Carr",
    "club-x-val": "Valdor SC", "club-x-ves": "Vesterholm", "club-x-kes": "Kesh Athletic",
    "club-x-mer": "Merrow Port",
}
CLUB_NAMES = {**{c.club_id: c.name for c in CLUBS}, **OTHER_CLUBS}


def club_team(club_id: str, side: str) -> Team:
    """A club's squad, coach and team sheet; the same players whichever side of the fixture it is on.

    The two demo clubs come from the demo seed, built in the same order as the demo match.
    """
    if club_id in (HBC.club_id, ROV.club_id):
        rng = np.random.default_rng(DEMO_1021.seed)
        home = build_team(rng, side, HBC.club_id, HBC.name, HBC.short, HBC.color, HBC.formation, HBC.strength)
        if club_id == HBC.club_id:
            return home
        return build_team(rng, side, ROV.club_id, ROV.name, ROV.short, ROV.color, ROV.formation, ROV.strength)
    club = BY_ID[club_id]
    rng = np.random.default_rng([WORLD_SEED, CLUBS.index(club)])
    return build_team(rng, side, club.club_id, club.name, club.short, club.color, club.formation, club.strength)


@cache
def referees() -> tuple[Referee, ...]:
    """The league's referees; the first one is the demo match's."""
    demo = DEMO_1021.build().context.referee
    rng = np.random.default_rng([WORLD_SEED, 99])
    out = [demo]
    for k in range(2, 13):
        out.append(Referee(referee_id=f"ref-{k}", name=_name(rng), strictness=int(rng.integers(45, 76)),
                           card_tendency=int(rng.integers(45, 76)), advantage_tendency=int(rng.integers(40, 71)),
                           big_match_experience=int(rng.integers(30, 86))))
    return tuple(out)


@dataclass(frozen=True)
class Fixture:
    season: int
    matchday: int
    home: str
    away: str
    seed: int


def schedule() -> list[Fixture]:
    """Double round robin (circle method): matchdays 20-38 replay 1-19 with home and away swapped.

    The rounds are ordered so that Rovers host Harbour City on matchday 11 and the return game,
    the demo, is matchday 30.
    """
    ids = [c.club_id for c in CLUBS]
    n = len(ids)
    rounds = []
    for r in range(n - 1):
        pairs = [(ids[i], ids[n - 1 - i]) if (r + i) % 2 == 0 else (ids[n - 1 - i], ids[i]) for i in range(n // 2)]
        rounds.append(pairs)
        ids = [ids[0], ids[-1], *ids[1:-1]]
    demo = {HBC.club_id, ROV.club_id}
    r0 = next(r for r, pairs in enumerate(rounds) if any(set(p) == demo for p in pairs))
    shift = (r0 - (DEMO_MATCHDAY - (n - 1) - 1)) % (n - 1)
    rounds = rounds[shift:] + rounds[:shift]
    first = DEMO_MATCHDAY - (n - 1) - 1
    rounds[first] = [(ROV.club_id, HBC.club_id) if set(p) == demo else p for p in rounds[first]]
    out = []
    for half in (0, 1):
        for r, pairs in enumerate(rounds):
            md = half * (n - 1) + r + 1
            for k, (h, a) in enumerate(pairs):
                h, a = (a, h) if half else (h, a)
                seed = DEMO_1021.seed if md == DEMO_MATCHDAY and {h, a} == demo else SEASON * 10000 + md * 100 + k
                out.append(Fixture(SEASON, md, h, a, seed))
    return out


def past_meetings() -> list[Fixture]:
    """Harbour City v Northgate Rovers in the two seasons before this one, home and away."""
    return [Fixture(year, md, h, a, year * 10000 + md * 100 + 99)
            for year in (SEASON - 2, SEASON - 1)
            for md, h, a in ((12, ROV.club_id, HBC.club_id), (31, HBC.club_id, ROV.club_id))]


def fixture_match(fx: Fixture) -> Match:
    """The match for a season fixture: the two squads, the home ground, a referee and a crowd."""
    rng = np.random.default_rng([fx.seed, 7])
    venue = BY_ID[fx.home]
    context = MatchContext(competition=COMPETITION, venue=venue.venue,
                           attendance=int(venue.capacity * rng.uniform(0.7, 1.0)),
                           referee=referees()[int(rng.integers(0, 12))])
    return Match(match_id=f"S{fx.season}-{fx.matchday:02d}-{BY_ID[fx.home].short}-{BY_ID[fx.away].short}",
                 seed=fx.seed, home=club_team(fx.home, "home"), away=club_team(fx.away, "away"),
                 context=context, status="scheduled")


# --- careers -------------------------------------------------------------------------------------

_GOALS_PER_GAME = {"GK": 0.0, "CB": 0.04, "LB": 0.03, "RB": 0.03, "LWB": 0.04, "RWB": 0.04, "DM": 0.05,
                   "CM": 0.09, "LM": 0.15, "RM": 0.15, "AM": 0.2, "LW": 0.25, "RW": 0.25, "ST": 0.4}
_DEMO_PEOPLE = (HBC.club_id, ROV.club_id)


def _past_club(rng: np.random.Generator, own: str, young: bool) -> str:
    """A club someone played for before: never the current club, never one of the demo pair
    (the demo's reunions are placed by hand in season.py), often the second tier when young."""
    league = [c.club_id for c in CLUBS if c.club_id not in (own, *_DEMO_PEOPLE)]
    other = list(OTHER_CLUBS)
    pool = other if young and rng.random() < 0.6 else league + other
    return str(rng.choice(pool))


def player_career(rng: np.random.Generator, player: Player, club_id: str) -> list[CareerStint]:
    """Clubs since turning professional at 18, oldest first; the last stint is the current club."""
    start = SEASON - (player.age - 18)
    joined = SEASON - int(rng.integers(0, min(6, SEASON - start) + 1))
    rate = _GOALS_PER_GAME[player.role]
    stints, year = [], start
    while year < joined:
        length = min(int(rng.choice([1, 2, 2, 3, 3, 4, 5])), joined - year)
        loan = length == 1 and rng.random() < 0.35
        club = _past_club(rng, club_id, young=year - start < 3)
        apps = int(length * rng.integers(10, 35))
        stints.append(CareerStint(
            stint_id=f"{player.player_id}-c{len(stints) + 1}", club_id=club, club_name=CLUB_NAMES[club],
            from_year=year, to_year=year + length, loan=loan, appearances=apps,
            goals=int(rng.binomial(apps, rate)) if rate else 0,
            departure="loan_end" if loan else str(rng.choice(["transfer"] * 5 + ["contract_end", "released"])),
            departure_mood=str(rng.choice(["amicable", "neutral", "acrimonious"], p=[0.45, 0.45, 0.10]))))
        year += length
    apps = int((SEASON - joined) * rng.integers(15, 34))
    stints.append(CareerStint(stint_id=f"{player.player_id}-c{len(stints) + 1}", club_id=club_id,
                              club_name=CLUB_NAMES[club_id], from_year=joined, appearances=apps,
                              goals=int(rng.binomial(apps, rate)) if rate else 0))
    return stints


def coach_career(rng: np.random.Generator, coach: Coach, club_id: str) -> list[CareerStint]:
    """Coaching jobs since about 40, oldest first; the last one is the current club."""
    start = SEASON - max(1, coach.age - int(rng.integers(36, 44)))
    joined = SEASON - int(rng.integers(0, min(4, SEASON - start) + 1))
    stints, year = [], start
    while year < joined:
        length = min(int(rng.integers(1, 5)), joined - year)
        club = _past_club(rng, club_id, young=year - start < 4)
        stints.append(CareerStint(
            stint_id=f"{coach.coach_id}-c{len(stints) + 1}", club_id=club, club_name=CLUB_NAMES[club],
            from_year=year, to_year=year + length, as_coach=True, appearances=int(length * rng.integers(30, 46)),
            departure=str(rng.choice(["sacked", "sacked", "resigned", "contract_end", "transfer"])),
            departure_mood=str(rng.choice(["amicable", "neutral", "acrimonious"], p=[0.35, 0.45, 0.20]))))
        year += length
    stints.append(CareerStint(stint_id=f"{coach.coach_id}-c{len(stints) + 1}", club_id=club_id,
                              club_name=CLUB_NAMES[club_id], from_year=joined, as_coach=True,
                              appearances=int((SEASON - joined) * rng.integers(30, 46))))
    return stints


def with_careers(team: Team) -> Team:
    """The team with every player's and the coach's career filled in (the same for either side)."""
    club = CLUBS.index(BY_ID[team.club_id])
    squad = [p.model_copy(update={"career": player_career(np.random.default_rng([WORLD_SEED, club, p.shirt_number, 1]),
                                                          p, team.club_id)})
             for p in team.squad]
    coach = team.coach.model_copy(update={"career": coach_career(np.random.default_rng([WORLD_SEED, club, 0, 2]),
                                                                 team.coach, team.club_id)})
    return team.model_copy(update={"squad": squad, "coach": coach})
