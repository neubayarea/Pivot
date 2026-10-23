"""Shared data models. This package is the single source of truth for the data format:
the JSON Schema and TypeScript types in packages/contracts are generated from it.
"""

from .common import PITCH_LENGTH, PITCH_WIDTH, Point, Side, zone_of
from .events import BodyPart, EventType, MatchEvent, PassHeight, PassType, PlayPattern, ShotOutcome
from .match import ROLE_POSITION, Match, Player, PlayerAttributes, Role, Score, Team
from .narrative import Audience, ExplanationSentence, Language, Narrative, ViewerPrefs
from .outputs import OverlayFeed, OverlayItem, Recap
from .pivots import MinuteMetric, Pivot, PivotCandidate
from .realtime import Envelope
from .scenarios import OutcomeDist, PlantSpec, Scenario, ScenarioSpec, SimResult
from .stats import STAT_UNITS, Claim, StatMetric, StatRef
from .traces import AgentTrace, Verdict, VerifierIssue
from .tracking import FRAME_RATE_HZ, BallPosition, PlayerPosition, TrackingFrame

# Every model exported to JSON Schema and TypeScript, in a stable order.
CONTRACT_MODELS = (
    Match, Team, Player, PlayerAttributes, Score,
    MatchEvent, TrackingFrame, PlayerPosition, BallPosition, MinuteMetric,
    StatRef, Claim,
    ViewerPrefs, ExplanationSentence, Narrative,
    PivotCandidate, Pivot,
    ScenarioSpec, PlantSpec, OutcomeDist, SimResult, Scenario,
    OverlayItem, OverlayFeed, Recap,
    VerifierIssue, Verdict, AgentTrace,
    Envelope,
)

__all__ = [
    "CONTRACT_MODELS", "FRAME_RATE_HZ", "PITCH_LENGTH", "PITCH_WIDTH", "ROLE_POSITION",
    "STAT_UNITS", "zone_of",
    "AgentTrace", "Audience", "BallPosition", "BodyPart", "Claim", "Envelope", "EventType",
    "ExplanationSentence", "Language", "Match", "MatchEvent", "MinuteMetric", "Narrative",
    "OutcomeDist", "OverlayFeed", "OverlayItem", "PassHeight", "PassType", "Pivot",
    "PivotCandidate", "PlantSpec", "PlayPattern", "Player", "PlayerAttributes", "PlayerPosition",
    "Point", "Recap", "Role", "Scenario", "ScenarioSpec",
    "Score", "ShotOutcome", "Side", "SimResult", "StatMetric", "StatRef", "Team",
    "TrackingFrame", "Verdict", "VerifierIssue", "ViewerPrefs",
]
