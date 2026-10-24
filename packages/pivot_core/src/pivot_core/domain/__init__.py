"""Shared data models. This package is the single source of truth for the data format:
the JSON Schema and TypeScript types in packages/contracts are generated from it.
"""

from .common import (
    GRID_COLS, GRID_ROWS, PITCH_LENGTH, PITCH_WIDTH, Area, Lane, Period, Point, Side, Third,
    area_of, attacking_view, clock_label, lane_of, third_of, zone_of,
)
from .context import (
    Competition, ContextEffect, HeadToHead, MatchContext, OffFieldEvent, PastMeeting,
    PreMatchCondition, TeamForm,
)
from .events import (
    BodyPart, EventType, MatchEvent, PassHeight, PassTechnique, PassType, PlayPattern,
    ShotOutcome, ShotTechnique,
)
from .lineup import (
    LineupSlot, PlayerInstruction, SetPieceTactics, Substitution, TeamSheet, TeamTactics,
)
from .match import Match, PeriodInfo, Score, Team
from .narrative import Audience, ExplanationSentence, Language, Narrative, ViewerPrefs
from .officials import FoulDetail, InjuryInfo, Referee, VarReview
from .outputs import (
    OVERLAY_CARD_SECONDS, OverlayCard, OverlayFeed, OverlayFrame, OverlayItem, OverlayScoreboard,
    OverlayTimeline, PlayerMatchStats, Recap,
)
from .people import (
    ROLE_POSITION, AttackingAttributes, AttributeSummary, CareerStint, Coach, CoachAttributes,
    DefendingAttributes, GoalkeepingAttributes, MentalityAttributes, MovementAttributes,
    Personality, Player, PlayerAttributes, PowerAttributes, Relationship, Role, SkillAttributes,
    Trait,
)
from .pivots import MinuteMetric, Pivot, PivotCandidate
from .realtime import Envelope
from .scenarios import OutcomeDist, PlantSpec, Scenario, ScenarioSpec, SimResult
from .stats import STAT_UNITS, Claim, StatMetric, StatRef
from .traces import AgentTrace, Verdict, VerifierIssue
from .tracking import FRAME_RATE_HZ, BallPosition, PlayerPosition, TrackingFrame

# Every model exported to JSON Schema and TypeScript, in a stable order.
CONTRACT_MODELS = (
    Match, Team, Score, PeriodInfo,
    Player, PlayerAttributes, AttributeSummary, Personality, Coach, CoachAttributes,
    CareerStint, Relationship,
    TeamSheet, LineupSlot, TeamTactics, SetPieceTactics, PlayerInstruction, Substitution,
    MatchContext, Competition, PreMatchCondition, OffFieldEvent, ContextEffect,
    TeamForm, HeadToHead, PastMeeting,
    Referee, FoulDetail, VarReview, InjuryInfo,
    MatchEvent, TrackingFrame, PlayerPosition, BallPosition, MinuteMetric,
    StatRef, Claim,
    ViewerPrefs, ExplanationSentence, Narrative,
    PivotCandidate, Pivot,
    ScenarioSpec, PlantSpec, OutcomeDist, SimResult, Scenario,
    OverlayItem, OverlayFeed, OverlayCard, OverlayScoreboard, OverlayFrame, OverlayTimeline,
    PlayerMatchStats, Recap,
    VerifierIssue, Verdict, AgentTrace,
    Envelope,
)

__all__ = [
    "CONTRACT_MODELS", "FRAME_RATE_HZ", "OVERLAY_CARD_SECONDS", "GRID_COLS", "GRID_ROWS", "PITCH_LENGTH", "PITCH_WIDTH",
    "ROLE_POSITION", "STAT_UNITS",
    "area_of", "attacking_view", "clock_label", "lane_of", "third_of", "zone_of",
    "AgentTrace", "Area", "AttackingAttributes", "AttributeSummary", "Audience", "BallPosition",
    "BodyPart", "CareerStint", "Claim", "Coach", "CoachAttributes", "Competition",
    "ContextEffect", "DefendingAttributes", "FoulDetail", "HeadToHead", "InjuryInfo", "Envelope", "EventType", "ExplanationSentence",
    "GoalkeepingAttributes", "Lane", "Language", "LineupSlot", "Match", "MatchContext",
    "MatchEvent", "MentalityAttributes", "MinuteMetric", "MovementAttributes", "Narrative",
    "OffFieldEvent", "OutcomeDist", "PastMeeting", "PlayerMatchStats", "Referee", "SetPieceTactics",
    "TeamForm", "VarReview", "OverlayCard", "OverlayFeed", "OverlayFrame", "OverlayItem",
    "OverlayScoreboard", "OverlayTimeline", "PassHeight", "PassTechnique", "PassType", "ShotTechnique",
    "Period", "PeriodInfo",
    "Personality", "Pivot", "PivotCandidate", "PlantSpec", "PlayPattern", "Player",
    "PlayerAttributes", "PlayerInstruction", "PlayerPosition", "Point", "PowerAttributes",
    "PreMatchCondition", "Recap", "Relationship", "Role", "Scenario", "ScenarioSpec", "Score",
    "ShotOutcome", "Side", "SimResult", "SkillAttributes", "StatMetric", "StatRef",
    "Substitution", "Team", "TeamSheet", "TeamTactics", "Third", "TrackingFrame", "Trait",
    "Verdict", "VerifierIssue", "ViewerPrefs",
]
