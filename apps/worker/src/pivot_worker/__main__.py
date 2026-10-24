"""Run the worker: `PIVOT_PROFILE=local uv run python -m pivot_worker [--demo]`.

With `--demo` it enqueues one sample candidate on the local queue, handles it and prints the
stored pivot, traces and pushed envelopes, then exits. Without it, it consumes until Ctrl-C.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal

from pivot_adapters import build_adapters
from pivot_core.domain import PivotCandidate
from pivot_core.ports import PIVOT_CANDIDATES

from .pipeline import FakePipeline
from .worker import Worker

SAMPLE = PivotCandidate(
    match_id="demo-1021", minute=63, direction="home", cusum_stat=4.2, swing=0.41,
    key_event_ids=["demo-1021:e512", "demo-1021:e519"], window=(55, 71),
)


async def demo(worker: Worker) -> None:
    adapters = worker.adapters
    async with adapters.live.subscribe(SAMPLE.match_id) as sub:
        await adapters.queue.send(PIVOT_CANDIDATES, f"{SAMPLE.match_id}:{SAMPLE.minute}",
                                  SAMPLE.model_dump(mode="json", round_trip=True))
        await worker.run_once(timeout=1)
        pivot = await adapters.matches.get_pivot(SAMPLE.match_id, f"{SAMPLE.match_id}:p{SAMPLE.minute}")
        print(f"pivot {pivot.pivot_id}: {pivot.status}, severity {pivot.severity}, \"{pivot.narrative.headline}\"")
        for t in await adapters.traces.list_traces(SAMPLE.match_id):
            print(f"  trace {t.trace_id} {t.agent:<9} {t.status:<8} {t.output_summary}")
        while True:
            try:
                env = await sub.get(timeout=0.01)
            except TimeoutError:
                break
            print(f"  push #{env.seq} {env.type}")


async def serve(worker: Worker) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
    logging.getLogger("pivot_worker").info("consuming %s (profile %s)", PIVOT_CANDIDATES, worker.adapters.profile)
    await worker.run(stop)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pivot_worker")
    parser.add_argument("--demo", action="store_true", help="handle one sample candidate and exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    worker = Worker(build_adapters(), FakePipeline())
    asyncio.run(demo(worker) if args.demo else serve(worker))


if __name__ == "__main__":
    main()
