"""In-memory `MatchRepository` and `TraceRepository`. Data is lost when the process exits."""

from __future__ import annotations

from collections import defaultdict

from pivot_core.domain import AgentTrace, Match, MatchEvent, MinuteMetric, Narrative, Pivot, ViewerPrefs


class InMemoryMatchRepository:
    def __init__(self) -> None:
        self._matches: dict[str, Match] = {}                                         # insertion order = storage order
        self._metrics: defaultdict[str, dict[int, MinuteMetric]] = defaultdict(dict)  # match_id -> minute -> metric
        self._events: defaultdict[str, dict[int, MatchEvent]] = defaultdict(dict)   # match_id -> seq -> event
        self._pivots: defaultdict[str, dict[str, Pivot]] = defaultdict(dict)        # match_id -> pivot_id -> pivot
        # match_id -> (pivot_id, prefs) -> one personalised version of the pivot's text
        self._narratives: defaultdict[str, dict[tuple[str, ViewerPrefs], Narrative]] = defaultdict(dict)

    async def upsert_match(self, match: Match) -> None:
        self._matches.pop(match.match_id, None)   # re-insert so the latest write comes first in list_matches
        self._matches[match.match_id] = match.model_copy(deep=True)

    async def get_match(self, match_id: str) -> Match | None:
        match = self._matches.get(match_id)
        return match.model_copy(deep=True) if match else None

    async def list_matches(self) -> list[Match]:
        return [m.model_copy(deep=True) for m in reversed(self._matches.values())]

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

    async def upsert_metrics(self, metrics: list[MinuteMetric]) -> None:
        for metric in metrics:
            self._metrics[metric.match_id][metric.minute] = metric.model_copy(deep=True)

    async def list_metrics(self, match_id: str) -> list[MinuteMetric]:
        stored = self._metrics.get(match_id, {})
        return [stored[minute].model_copy(deep=True) for minute in sorted(stored)]

    async def upsert_pivot(self, pivot: Pivot) -> None:
        self._pivots[pivot.match_id][pivot.pivot_id] = pivot.model_copy(deep=True)

    async def get_pivot(self, match_id: str, pivot_id: str) -> Pivot | None:
        pivot = self._pivots.get(match_id, {}).get(pivot_id)
        return pivot.model_copy(deep=True) if pivot else None

    async def list_pivots(self, match_id: str) -> list[Pivot]:
        pivots = sorted(self._pivots.get(match_id, {}).values(), key=lambda p: (p.minute, p.pivot_id))
        return [p.model_copy(deep=True) for p in pivots]

    async def upsert_narrative(self, match_id: str, pivot_id: str, narrative: Narrative) -> None:
        self._narratives[match_id][(pivot_id, narrative.prefs)] = narrative.model_copy(deep=True)

    async def get_narrative(self, match_id: str, pivot_id: str, prefs: ViewerPrefs) -> Narrative | None:
        narrative = self._narratives.get(match_id, {}).get((pivot_id, prefs))
        return narrative.model_copy(deep=True) if narrative else None


class InMemoryTraceRepository:
    def __init__(self) -> None:
        self._traces: defaultdict[str, dict[str, AgentTrace]] = defaultdict(dict)   # match_id -> trace_id -> trace

    async def append_trace(self, trace: AgentTrace) -> None:
        self._traces[trace.match_id][trace.trace_id] = trace.model_copy(deep=True)

    async def list_traces(self, match_id: str, chain_id: str | None = None) -> list[AgentTrace]:
        traces = [t for t in self._traces.get(match_id, {}).values() if chain_id is None or t.chain_id == chain_id]
        return [t.model_copy(deep=True) for t in sorted(traces, key=lambda t: (t.chain_id, t.step))]
