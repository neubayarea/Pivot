"""Worker shell: consume `pivot-candidates`, run the Detect pipeline, store, trace and push (ADR-0003).

Per message:
1. Skip (and complete) it if its pivot already reached a final status: delivery is at least once.
2. Run the pipeline under a lock-renewal loop, writing one `AgentTrace` per agent step.
3. Store the pivot, push `pivot.confirmed` / `pivot.degraded` / `pivot.rejected`, then complete.
On failure the message is abandoned for another try, and dead-lettered after `max_deliveries`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from pivot_adapters import Adapters
from pivot_core.domain import AgentTrace, Envelope, Pivot, PivotCandidate
from pivot_core.ports import PIVOT_CANDIDATES, QueueMessage

from .pipeline import Pipeline, Step, pivot_id_of

log = logging.getLogger("pivot_worker")

FINAL_STATUSES = ("confirmed", "degraded", "rejected")
MAX_DELIVERIES = 5            # pivot-candidates, ADR-0003
LOCK_RENEW_SECONDS = 20.0     # well inside the 60 s Service Bus lock


class Worker:
    def __init__(self, adapters: Adapters, pipeline: Pipeline, *, max_deliveries: int = MAX_DELIVERIES,
                 lock_renew_seconds: float = LOCK_RENEW_SECONDS) -> None:
        self.adapters = adapters
        self.pipeline = pipeline
        self.max_deliveries = max_deliveries
        self.lock_renew_seconds = lock_renew_seconds
        # Envelope seq per match. In-process for now; a shared sequence comes with the cloud adapters.
        self._seq: defaultdict[str, int] = defaultdict(int)

    async def run(self, stop: asyncio.Event, poll_seconds: float = 1.0) -> None:
        while not stop.is_set():
            await self.run_once(timeout=poll_seconds)

    async def run_once(self, timeout: float | None = None) -> bool:
        """Receive and handle one message. Returns False if none arrived within `timeout`."""
        message = await self.adapters.queue.receive(PIVOT_CANDIDATES, timeout=timeout)
        if message is None:
            return False
        await self.handle(message)
        return True

    async def handle(self, message: QueueMessage) -> None:
        queue = self.adapters.queue
        try:
            candidate = PivotCandidate.model_validate(message.body)
        except ValidationError as exc:
            log.error("dead-lettering malformed candidate %s: %s", message.message_id, exc)
            await queue.dead_letter(message, f"invalid body: {exc.error_count()} errors")
            return

        existing = await self.adapters.matches.get_pivot(candidate.match_id, pivot_id_of(candidate))
        if existing is not None and existing.status in FINAL_STATUSES:
            log.info("skipping %s: pivot already %s", message.message_id, existing.status)
            await queue.complete(message)
            return

        chain_id = f"detect:{candidate.match_id}:{candidate.minute}:d{message.delivery_count}"
        steps = _ChainTraces(self, candidate, chain_id)
        try:
            async with self._renewing(message):
                pivot = await self.pipeline.run(candidate, chain_id, steps.record)
                await self.adapters.matches.upsert_pivot(pivot)
                await self._publish_pivot(pivot)
        except Exception as exc:
            log.exception("candidate %s failed on delivery %d", message.message_id, message.delivery_count)
            await steps.record(Step(steps.last_agent, f"error: {exc!r}"[:500], status="error"))
            if message.delivery_count >= self.max_deliveries:
                await queue.dead_letter(message, f"failed {message.delivery_count} times: {exc!r}"[:500])
            else:
                await queue.abandon(message)
            return
        await queue.complete(message)
        log.info("candidate %s -> %s (%s)", message.message_id, pivot.pivot_id, pivot.status)

    @asynccontextmanager
    async def _renewing(self, message: QueueMessage):
        async def loop() -> None:
            while True:
                await asyncio.sleep(self.lock_renew_seconds)
                await self.adapters.queue.renew_lock(message)

        task = asyncio.create_task(loop())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def publish(self, type_: str, match_id: str, payload: dict[str, Any]) -> None:
        self._seq[match_id] += 1
        await self.adapters.live.publish(Envelope(
            type=type_, match_id=match_id, seq=self._seq[match_id],
            ts=datetime.now(UTC).isoformat(), payload=payload,
        ))

    async def _publish_pivot(self, pivot: Pivot) -> None:
        if pivot.status == "rejected":
            await self.publish("pivot.rejected", pivot.match_id, {"pivotId": pivot.pivot_id})
        else:
            await self.publish(f"pivot.{pivot.status}", pivot.match_id, pivot.model_dump(mode="json"))


class _ChainTraces:
    """Turns pipeline steps into numbered `AgentTrace`s: stored, then pushed as `trace.appended`."""

    def __init__(self, worker: Worker, candidate: PivotCandidate, chain_id: str) -> None:
        self.worker = worker
        self.candidate = candidate
        self.chain_id = chain_id
        self.step = 0
        self.last_agent: Any = "judge"   # AgentName has no "worker" yet; errors go on the last agent
        self._t = time.monotonic()

    async def record(self, step: Step) -> None:
        now = time.monotonic()
        trace = AgentTrace(
            trace_id=f"{self.chain_id}:{self.step}", chain_id=self.chain_id, step=self.step,
            match_id=self.candidate.match_id, agent=step.agent, model=step.model, prompt_hash=step.prompt_hash,
            input_ref=pivot_id_of(self.candidate), output_summary=step.output_summary,
            latency_ms=int((now - self._t) * 1000), tokens=step.tokens, status=step.status, verdict=step.verdict,
        )
        self.step += 1
        self.last_agent = step.agent
        self._t = now
        await self.worker.adapters.traces.append_trace(trace)
        await self.worker.publish("trace.appended", trace.match_id, trace.model_dump(mode="json"))
