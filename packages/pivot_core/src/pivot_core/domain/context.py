"""Everything around the match that is not on the pitch: competition, stakes, fitness and
morale going in, off-field news, and the ties between people.

All of it is fictional. The simulator turns these factors into a small, explicit list of
`ContextEffect`s at kick-off, so every effect it applied can be shown and cited.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import Model, Side
from .officials import InjuryInfo, Referee
from .people import Relationship

CompetitionLevel = Literal[
    "league", "domestic_cup", "continental_club", "international_tournament", "friendly",
]
Stage = Literal[
    "league", "group", "round_of_32", "round_of_16", "quarter_final", "semi_final", "final", "friendly",
]


class Competition(Model):
    competition_id: str
    name: str                                 # fictional, never a real competition brand
    level: CompetitionLevel
    tier: Annotated[int, Field(ge=1, le=5)] = 1   # 1 = top flight
    stage: Stage = "league"
    importance: Annotated[int, Field(ge=1, le=5)]  # 5 = final; scales the big-match effect
    neutral_venue: bool = False
    # What happens after a draw at 90 minutes. Knockout ties usually play 2 x 15 minutes of
    # extra time and then a penalty shootout; league games just end.
    extra_time: bool = False
    penalty_shootout: bool = False


class PreMatchCondition(Model):
    player_id: str
    fitness: Annotated[float, Field(ge=0, le=1)] = 1.0     # physical freshness at kick-off
    sharpness: Annotated[float, Field(ge=0, le=1)] = 1.0   # match rhythm; low after injury or bench time
    morale: Annotated[int, Field(ge=1, le=99)] = 60
    recent_ratings: Annotated[list[float], Field(max_length=5)] = []   # last five, 1-10, newest last
    days_since_last_match: Annotated[int, Field(ge=0)] | None = None
    carrying_knock: bool = False
    availability: Literal["available", "injured", "suspended", "ill", "not_selected"] = "available"
    injury: InjuryInfo | None = None          # current injury, if any
    on_yellow_card_threshold: bool = False    # one more booking means a suspension


NewsKind = Literal[
    "nightlife", "late_return", "family_matter", "contract_dispute", "transfer_rumour",
    "public_criticism", "fan_conflict", "training_ground_clash", "disciplinary",
    "illness", "charity", "milestone", "new_contract",
]


class OffFieldEvent(Model):
    """A fictional news item about a player or coach before the match."""

    news_id: str
    subject_id: str                           # player_id or coach_id
    kind: NewsKind
    hours_before_kickoff: Annotated[int, Field(ge=0, le=24 * 30)]
    severity: Annotated[int, Field(ge=1, le=3)] = 1
    sentiment: Literal["negative", "neutral", "positive"]
    public: bool = True                       # known to the media and the crowd
    headline: Annotated[str, Field(max_length=120)]


Result = Literal["W", "D", "L"]


class TeamForm(Model):
    side: Side
    last_results: Annotated[list[Result], Field(max_length=5)] = []   # newest last
    goals_for_last5: Annotated[int, Field(ge=0)] = 0
    goals_against_last5: Annotated[int, Field(ge=0)] = 0
    league_position: Annotated[int, Field(ge=1, le=40)] | None = None
    points: Annotated[int, Field(ge=0)] | None = None


class PastMeeting(Model):
    season: str                               # "2025-26"
    home_club_id: str
    away_club_id: str
    home_goals: Annotated[int, Field(ge=0)]
    away_goals: Annotated[int, Field(ge=0)]
    competition_id: str | None = None


class HeadToHead(Model):
    """Record between the two clubs, counted from this match's home side."""

    played: Annotated[int, Field(ge=0)] = 0
    home_wins: Annotated[int, Field(ge=0)] = 0
    draws: Annotated[int, Field(ge=0)] = 0
    away_wins: Annotated[int, Field(ge=0)] = 0
    last_meetings: Annotated[list[PastMeeting], Field(max_length=10)] = []   # newest last


EffectSource = Literal[
    "former_club", "former_teammate", "former_coach", "rivalry", "competition",
    "stakes", "crowd", "off_field", "form", "fatigue", "weather", "referee", "head_to_head", "injury",
]
EffectTarget = Literal[
    "composure", "motivation", "concentration", "fitness", "aggression", "chemistry",
    "card_risk", "error_rate",
]


class ContextEffect(Model):
    """One modifier the simulator applied because of the context. Small by design (|delta| <= 0.15)."""

    effect_id: str
    subject_id: str                           # player_id, coach_id, or a side for team-wide effects
    source: EffectSource
    source_ref: str | None = None             # news_id, stint_id or relationship_id behind it
    target: EffectTarget
    delta: Annotated[float, Field(ge=-0.15, le=0.15)]
    note: Annotated[str, Field(max_length=120)]   # plain-English reason, e.g. "first game back at former club"


class MatchContext(Model):
    competition: Competition
    venue: str                                # fictional stadium
    attendance: Annotated[int, Field(ge=0)] = 0
    derby: bool = False
    stakes: Literal["none", "title_race", "relegation", "qualification", "knockout"] = "none"
    weather: Literal["clear", "rain", "wind", "heat", "snow"] = "clear"
    pitch: Literal["good", "worn", "heavy", "artificial"] = "good"
    referee: Referee | None = None
    form: Annotated[list[TeamForm], Field(max_length=2)] = []   # one per side
    head_to_head: HeadToHead | None = None
    conditions: list[PreMatchCondition] = []
    news: list[OffFieldEvent] = []
    relationships: list[Relationship] = []    # ties between people in this match
    effects: list[ContextEffect] = []         # filled by the simulator at kick-off
