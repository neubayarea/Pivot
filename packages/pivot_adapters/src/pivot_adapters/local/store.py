"""In-memory `MatchRepository` and `TraceRepository`. Data is lost when the process exits."""

from __future__ import annotations

from collections import defaultdict

from pivot_core.domain import AgentTrace, MatchEvent, Pivot


class InMemoryMatchRepository:
    def __init__(self) -> None:
        self._events: defaultdict[str, dict[int, MatchEvent]] = defaultdict(dict)   # match_id -> seq -> event
        self._pivots: defaultdict[str, dict[str, Pivot]] = defaultdict(dict)        # match_id -> pivot_id -> pivot

    async def append_events(self, events: list[MatchEvent]) -> int:
        added = 0
        for event in events:
            stored = self._events[event.match_id]
            if event.seq not in stored:
                stored[event.seq] = event.model_copy(deep=True)
                added += 1
        return added

    async def list_events(self, match_id: str, since_seq: int = -1) -> list[MatchEvent]:
        stored = self._events.get(match_id, {})
        return [stored[seq].model_copy(deep=True) for seq in sorted(stored) if seq > since_seq]

    async def upsert_pivot(self, pivot: Pivot) -> None:
        self._pivots[pivot.match_id][pivot.pivot_id] = pivot.model_copy(deep=True)

    async def get_pivot(self, match_id: str, pivot_id: str) -> Pivot | None:
        pivot = self._pivots.get(match_id, {}).get(pivot_id)
        return pivot.model_copy(deep=True) if pivot else None

    async def list_pivots(self, match_id: str) -> list[Pivot]:
        pivots = sorted(self._pivots.get(match_id, {}).values(), key=lambda p: (p.minute, p.pivot_id))
        return [p.model_copy(deep=True) for p in pivots]


class InMemoryTraceRepository:
    def __init__(self) -> None:
        self._traces: defaultdict[str, dict[str, AgentTrace]] = defaultdict(dict)   # match_id -> trace_id -> trace

    async def append_trace(self, trace: AgentTrace) -> None:
        self._traces[trace.match_id][trace.trace_id] = trace.model_copy(deep=True)

    async def list_traces(self, match_id: str, chain_id: str | None = None) -> list[AgentTrace]:
        traces = [t for t in self._traces.get(match_id, {}).values() if chain_id is None or t.chain_id == chain_id]
        return [t.model_copy(deep=True) for t in sorted(traces, key=lambda t: (t.chain_id, t.step))]
