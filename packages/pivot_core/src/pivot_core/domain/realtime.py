"""Envelope for every message pushed to browsers (local WebSocket or Web PubSub)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from .common import Model

MessageType = Literal[
    "match.status", "event.batch", "tracking.frame", "metric.updated",
    "pivot.pending", "pivot.confirmed", "pivot.degraded", "pivot.rejected",
    "scenario.progress", "scenario.completed", "trace.appended", "recap.ready",
]


class Envelope(Model):
    type: MessageType
    match_id: str
    seq: Annotated[int, Field(ge=0)]          # per match; clients use it to detect gaps
    ts: str                                   # ISO 8601 server time
    payload: dict[str, Any]                   # shape depends on `type`, see architecture §7.2
