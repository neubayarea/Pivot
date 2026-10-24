"""In-process `LivePublisher` with per-match subscriptions, for the local WebSocket (A06).

Usage in a WebSocket handler:

    async with live.subscribe(match_id) as sub:
        async for envelope in sub:
            await ws.send_json(envelope.model_dump(mode="json"))

The publisher is the single hub of profile L, so it owns the per-match `seq`: each envelope
leaves with `seq = max(its seq, last seq + 1)`, which keeps seq strictly increasing even when
several publishers (simulator, worker) count on their own. It also keeps the last `history`
envelopes per match so a reconnecting client can `replay(match_id, since_seq)` what it missed.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pivot_core.domain import Envelope


class Subscription:
    """Envelopes for one match, in publish order. A slow subscriber that falls `maxsize`
    behind loses the newest messages and must catch up through `sinceSeq` (architecture §8)."""

    def __init__(self, match_id: str, maxsize: int) -> None:
        self.match_id = match_id
        self.dropped = 0
        self._queue: asyncio.Queue[Envelope] = asyncio.Queue(maxsize)

    async def get(self, timeout: float | None = None) -> Envelope:
        return await asyncio.wait_for(self._queue.get(), timeout)

    def __aiter__(self) -> AsyncIterator[Envelope]:
        return self

    async def __anext__(self) -> Envelope:
        return await self._queue.get()

    def _offer(self, envelope: Envelope) -> None:
        try:
            self._queue.put_nowait(envelope)
        except asyncio.QueueFull:
            self.dropped += 1


class InMemoryLivePublisher:
    def __init__(self, maxsize: int = 1000, history: int = 2000) -> None:
        self._maxsize = maxsize
        self._subs: defaultdict[str, set[Subscription]] = defaultdict(set)
        self._history: defaultdict[str, deque[Envelope]] = defaultdict(lambda: deque(maxlen=history))
        self._last_seq: dict[str, int] = {}

    async def publish(self, envelope: Envelope) -> None:
        last = self._last_seq.get(envelope.match_id, -1)
        if envelope.seq <= last:
            envelope = envelope.model_copy(update={"seq": last + 1})
        self._last_seq[envelope.match_id] = envelope.seq
        self._history[envelope.match_id].append(envelope)
        for sub in list(self._subs.get(envelope.match_id, ())):
            sub._offer(envelope)

    def replay(self, match_id: str, since_seq: int = -1) -> list[Envelope]:
        """Kept envelopes with seq > since_seq, in seq order. Older ones may have been evicted:
        if the first seq returned is not since_seq + 1, the client must refetch over REST."""
        return [e for e in self._history.get(match_id, ()) if e.seq > since_seq]

    def last_seq(self, match_id: str) -> int:
        """Seq of the last envelope published for the match, -1 if none."""
        return self._last_seq.get(match_id, -1)

    @asynccontextmanager
    async def subscribe(self, match_id: str) -> AsyncIterator[Subscription]:
        sub = Subscription(match_id, self._maxsize)
        self._subs[match_id].add(sub)
        try:
            yield sub
        finally:
            self._subs[match_id].discard(sub)
            if not self._subs[match_id]:
                del self._subs[match_id]

    def subscriber_count(self, match_id: str) -> int:
        return len(self._subs.get(match_id, ()))
