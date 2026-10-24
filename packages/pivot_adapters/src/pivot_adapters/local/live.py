"""In-process `LivePublisher` with per-match subscriptions, for the local WebSocket (A06).

Usage in a WebSocket handler:

    async with live.subscribe(match_id) as sub:
        async for envelope in sub:
            await ws.send_json(envelope.model_dump(mode="json"))
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
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
    def __init__(self, maxsize: int = 1000) -> None:
        self._maxsize = maxsize
        self._subs: defaultdict[str, set[Subscription]] = defaultdict(set)

    async def publish(self, envelope: Envelope) -> None:
        for sub in list(self._subs.get(envelope.match_id, ())):
            sub._offer(envelope)

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
