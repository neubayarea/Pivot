"""Shared data models. This package is the single source of truth for the data format:
the JSON Schema and TypeScript types in packages/contracts are generated from it.
"""

from .common import Side
from .events import EventType, MatchEvent
from .match import Match, Player, Score, Team
from .narrative import Audience, ExplanationSentence, Language, Narrative, ViewerPrefs
from .outputs import OverlayFeed, OverlayItem, Recap
from .pivots import MinuteMetric, Pivot, PivotCandidate
from .realtime import Envelope
from .scenarios import OutcomeDist, PlantSpec, Scenario, ScenarioSpec, SimResult
from .stats import STAT_UNITS, Claim, StatMetric, StatRef
from .traces import AgentTrace, Verdict, VerifierIssue

# Every model exported to JSON Schema and TypeScript, in a stable order.
CONTRACT_MODELS = (
    Match, Team, Player, Score,
    MatchEvent, MinuteMetric,
    StatRef, Claim,
    ViewerPrefs, ExplanationSentence, Narrative,
    PivotCandidate, Pivot,
    ScenarioSpec, PlantSpec, OutcomeDist, SimResult, Scenario,
    OverlayItem, OverlayFeed, Recap,
    VerifierIssue, Verdict, AgentTrace,
    Envelope,
)

__all__ = [
    "CONTRACT_MODELS", "STAT_UNITS",
    "AgentTrace", "Audience", "Claim", "Envelope", "EventType", "ExplanationSentence",
    "Language", "Match", "MatchEvent", "MinuteMetric", "Narrative", "OutcomeDist",
    "OverlayFeed", "OverlayItem", "Pivot", "PivotCandidate", "PlantSpec", "Player", "Recap",
    "Scenario", "ScenarioSpec", "Score", "Side", "SimResult", "StatMetric", "StatRef", "Team",
    "Verdict", "VerifierIssue", "ViewerPrefs",
]
