"""Ports: the only way the core and the apps reach queues, storage and realtime push.

Each port has a local adapter (packages/pivot_adapters/local) and, later, an Azure one
(Service Bus, Cosmos DB, Web PubSub; A08). Both must pass the same contract tests.
See ADR-0001 and architecture §4.2, §7.1, §7.2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .domain import AgentTrace, Envelope, Match, MatchEvent, MinuteMetric, Narrative, Pivot, ViewerPrefs

# Service Bus queue names (architecture §7.2).
PIVOT_CANDIDATES = "pivot-candidates"
SCENARIO_RUNS = "scenario-runs"


@dataclass
class QueueMessage:
    """A message handed out by `WorkQueue.receive`; settle it with complete or abandon."""

    queue: str
    message_id: str                           # business id, e.g. "{matchId}:{minute}"; duplicates are dropped
    # JSON-serialisable. Dump models with `model_dump(mode="json", round_trip=True)`: without
    # round_trip the computed fields are included and `model_validate` rejects them.
    body: dict[str, Any]
    delivery_count: int = 1
    lock_token: str = field(default="", repr=False)   # adapter-specific handle


class WorkQueue(Protocol):
    """Agent work queues with at-least-once delivery (Service Bus in the cloud)."""

    async def send(self, queue: str, message_id: str, body: dict[str, Any]) -> None:
        """Enqueue a message. A message_id already seen on this queue is ignored."""
        ...

    async def receive(self, queue: str, timeout: float | None = None) -> QueueMessage | None:
        """Lock and return the next message, or None if nothing arrives within `timeout` seconds."""
        ...

    async def complete(self, message: QueueMessage) -> None:
        """Acknowledge: the message is done and will not be delivered again."""
        ...

    async def abandon(self, message: QueueMessage) -> None:
        """Release the lock so the message is delivered again."""
        ...

    async def renew_lock(self, message: QueueMessage) -> None:
        """Extend the lock while a long job runs (Service Bus locks expire after 60 s, ADR-0003)."""
        ...

    async def dead_letter(self, message: QueueMessage, reason: str) -> None:
        """Settle a message that keeps failing: it moves aside and is not delivered again."""
        ...


class MatchRepository(Protocol):
    """Match data by match (Cosmos `match_data` in the cloud): the match, events, metrics and pivots."""

    async def upsert_match(self, match: Match) -> None:
        """Insert or replace by match_id (score, clock and status change as the match runs)."""
        ...

    async def get_match(self, match_id: str) -> Match | None: ...

    async def list_matches(self) -> list[Match]:
        """Every stored match, most recently stored first."""
        ...

    async def append_events(self, events: list[MatchEvent]) -> int:
        """Store events, skipping any (match_id, seq) already stored. Returns how many were new."""
        ...

    async def list_events(self, match_id: str, since_seq: int = -1) -> list[MatchEvent]:
        """Events with seq > since_seq, in seq order."""
        ...

    async def upsert_metrics(self, metrics: list[MinuteMetric]) -> None:
        """Insert or replace by (match_id, minute)."""
        ...

    async def list_metrics(self, match_id: str) -> list[MinuteMetric]:
        """Per-minute metrics of a match in minute order (the momentum timeline)."""
        ...

    async def upsert_pivot(self, pivot: Pivot) -> None:
        """Insert or replace by pivot_id (a pivot moves from pending to confirmed, ...)."""
        ...

    async def get_pivot(self, match_id: str, pivot_id: str) -> Pivot | None: ...

    async def list_pivots(self, match_id: str) -> list[Pivot]:
        """Pivots of a match in minute order."""
        ...

    async def upsert_narrative(self, match_id: str, pivot_id: str, narrative: Narrative) -> None:
        """Store one version of a pivot's text, keyed by (pivot_id, narrative.prefs); replaces the same key (A11)."""
        ...

    async def get_narrative(self, match_id: str, pivot_id: str, prefs: ViewerPrefs) -> Narrative | None:
        """The stored version for exactly these viewer preferences, or None."""
        ...


class TraceRepository(Protocol):
    """Agent traces (Cosmos `agent_traces` in the cloud)."""

    async def append_trace(self, trace: AgentTrace) -> None:
        """Insert or replace by trace_id."""
        ...

    async def list_traces(self, match_id: str, chain_id: str | None = None) -> list[AgentTrace]:
        """Traces of a match, optionally one chain, ordered by chain then step."""
        ...


class LivePublisher(Protocol):
    """Push envelopes to every browser watching a match (Web PubSub group per match in the cloud)."""

    async def publish(self, envelope: Envelope) -> None: ...


class LiveNegotiator(Protocol):
    """Hand a browser the address to open its realtime connection (Web PubSub client URL in the cloud)."""

    async def negotiate(self, match_id: str | None = None) -> str:
        """WebSocket URL the browser connects to; scoped to one match when `match_id` is given."""
        ...
