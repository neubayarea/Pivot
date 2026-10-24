"""Per-minute metrics, change-point candidates and confirmed pivots."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import Minute, MinuteWindow, Model, Side
from .narrative import Narrative


class MinuteMetric(Model):
    match_id: str
    minute: Minute
    momentum: Annotated[float, Field(ge=-1, le=1)]   # > 0 means home on top
    threat_home: float
    threat_away: float
    pressure_home: Annotated[int, Field(ge=0)]
    pressure_away: Annotated[int, Field(ge=0)]


class PivotCandidate(Model):
    """CUSUM alarm, queued for the Judge. Message id is "{match_id}:{minute}"."""

    match_id: str
    minute: Minute
    direction: Side                           # side the momentum swung towards
    cusum_stat: float
    swing: float                              # mean momentum 5 min after minus 5 min before
    key_event_ids: list[str]                  # goals, cards and substitutions in the window
    window: MinuteWindow


PivotStatus = Literal["pending", "confirmed", "rejected", "degraded"]


class Pivot(Model):
    pivot_id: str                             # "{match_id}:p{minute}"
    match_id: str
    minute: Minute
    direction: Side
    severity: Literal[1, 2, 3]
    status: PivotStatus
    trigger_event_ids: list[str]
    narrative: Narrative | None = None        # default version (analyst, en); None while pending
    chain_id: str
