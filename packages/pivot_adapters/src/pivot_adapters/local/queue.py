"""In-memory `WorkQueue`: asyncio queues with Service Bus-like dedup, locks and redelivery."""

from __future__ import annotations

import asyncio
import copy
import itertools
from collections import defaultdict
from typing import Any

from pivot_core.ports import QueueMessage


class InMemoryWorkQueue:
    def __init__(self) -> None:
        self._ready: defaultdict[str, asyncio.Queue[QueueMessage]] = defaultdict(asyncio.Queue)
        self._seen: defaultdict[str, set[str]] = defaultdict(set)      # message ids ever sent, per queue
        self._locked: dict[str, QueueMessage] = {}                      # lock_token -> message
        self._tokens = itertools.count(1)

    async def send(self, queue: str, message_id: str, body: dict[str, Any]) -> None:
        if message_id in self._seen[queue]:
            return
        self._seen[queue].add(message_id)
        # Copy so later changes by the sender do not leak into the queued message.
        self._ready[queue].put_nowait(QueueMessage(queue, message_id, copy.deepcopy(body), delivery_count=0))

    async def receive(self, queue: str, timeout: float | None = None) -> QueueMessage | None:
        try:
            message = await asyncio.wait_for(self._ready[queue].get(), timeout)
        except TimeoutError:
            return None
        message.delivery_count += 1
        message.lock_token = str(next(self._tokens))
        self._locked[message.lock_token] = message
        return message

    async def complete(self, message: QueueMessage) -> None:
        self._take_lock(message)

    async def abandon(self, message: QueueMessage) -> None:
        self._ready[message.queue].put_nowait(self._take_lock(message))

    def _take_lock(self, message: QueueMessage) -> QueueMessage:
        locked = self._locked.pop(message.lock_token, None)
        if locked is None:
            raise ValueError(f"message {message.message_id!r} is not locked (already settled?)")
        return locked
