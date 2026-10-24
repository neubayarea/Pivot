import asyncio

from pivot_adapters import build_adapters
from pivot_core.domain import PivotCandidate
from pivot_core.ports import PIVOT_CANDIDATES
from pivot_worker.__main__ import main
from pivot_worker.pipeline import FakePipeline, Step
from pivot_worker.worker import Worker

CANDIDATE = PivotCandidate(
    match_id="m1", minute=55, direction="away", cusum_stat=3.1, swing=-0.3,
    key_event_ids=["m1:e10"], window=(47, 63),
)
BODY = CANDIDATE.model_dump(mode="json", round_trip=True)


class CountingPipeline(FakePipeline):
    def __init__(self, failures: int = 0, delay: float = 0) -> None:
        self.calls = 0
        self.failures = failures
        self.delay = delay

    async def run(self, candidate, chain_id, record):
        self.calls += 1
        await asyncio.sleep(self.delay)
        if self.calls <= self.failures:
            await record(Step("judge", "thinking", model="fake"))
            raise RuntimeError("model timeout")
        return await super().run(candidate, chain_id, record)


def make(pipeline, **kw):
    adapters = build_adapters("local")
    return adapters, Worker(adapters, pipeline, **kw)


def test_success_stores_traces_in_order_and_pushes():
    async def run():
        adapters, worker = make(CountingPipeline())
        async with adapters.live.subscribe("m1") as sub:
            await adapters.queue.send(PIVOT_CANDIDATES, "m1:55", BODY)
            assert await worker.run_once(timeout=1)
            pivot = await adapters.matches.get_pivot("m1", "m1:p55")
            assert (pivot.status, pivot.severity, pivot.direction) == ("confirmed", 2, "away")
            traces = await adapters.traces.list_traces("m1")
            assert [(t.step, t.agent) for t in traces] == [(0, "judge"), (1, "explainer"), (2, "verifier")]
            assert {t.chain_id for t in traces} == {pivot.chain_id}
            pushed = [await sub.get(timeout=1) for _ in range(4)]
            assert [e.type for e in pushed] == ["trace.appended"] * 3 + ["pivot.confirmed"]
            assert [e.seq for e in pushed] == [1, 2, 3, 4]
            assert pushed[-1].payload["pivot_id"] == "m1:p55"
        assert await adapters.queue.receive(PIVOT_CANDIDATES, timeout=0.01) is None   # completed
    asyncio.run(run())


def test_duplicate_candidate_is_processed_once():
    async def run():
        pipeline = CountingPipeline()
        adapters, worker = make(pipeline)
        await adapters.queue.send(PIVOT_CANDIDATES, "m1:55", BODY)
        await adapters.queue.send(PIVOT_CANDIDATES, "m1:55", BODY)          # dropped by queue dedup
        await adapters.queue.send(PIVOT_CANDIDATES, "m1:55-late", BODY)     # outside the dedup window
        while await worker.run_once(timeout=0.01):
            pass
        assert pipeline.calls == 1
        assert len(await adapters.traces.list_traces("m1")) == 3
    asyncio.run(run())


def test_failure_is_retried_then_succeeds():
    async def run():
        pipeline = CountingPipeline(failures=2)
        adapters, worker = make(pipeline)
        await adapters.queue.send(PIVOT_CANDIDATES, "m1:55", BODY)
        while await worker.run_once(timeout=0.01):
            pass
        assert pipeline.calls == 3
        assert (await adapters.matches.get_pivot("m1", "m1:p55")).status == "confirmed"
        errors = [t for t in await adapters.traces.list_traces("m1") if t.status == "error"]
        assert [t.chain_id for t in errors] == ["detect:m1:55:d1", "detect:m1:55:d2"]
    asyncio.run(run())


def test_repeated_failure_goes_to_dead_letter():
    async def run():
        pipeline = CountingPipeline(failures=99)
        adapters, worker = make(pipeline, max_deliveries=3)
        await adapters.queue.send(PIVOT_CANDIDATES, "m1:55", BODY)
        while await worker.run_once(timeout=0.01):
            pass
        assert pipeline.calls == 3
        assert [m.message_id for m, _ in adapters.queue.dead_letters[PIVOT_CANDIDATES]] == ["m1:55"]
        assert await adapters.matches.get_pivot("m1", "m1:p55") is None
    asyncio.run(run())


def test_malformed_body_is_dead_lettered_without_retry():
    async def run():
        pipeline = CountingPipeline()
        adapters, worker = make(pipeline)
        await adapters.queue.send(PIVOT_CANDIDATES, "bad", {"match_id": "m1"})
        assert await worker.run_once(timeout=1)
        assert pipeline.calls == 0
        assert len(adapters.queue.dead_letters[PIVOT_CANDIDATES]) == 1
    asyncio.run(run())


def test_lock_is_renewed_during_long_runs():
    async def run():
        adapters, worker = make(CountingPipeline(delay=0.1), lock_renew_seconds=0.02)
        renewals = []
        renew = adapters.queue.renew_lock

        async def spy(message):
            renewals.append(message.message_id)
            await renew(message)

        adapters.queue.renew_lock = spy
        await adapters.queue.send(PIVOT_CANDIDATES, "m1:55", BODY)
        await worker.run_once(timeout=1)
        assert len(renewals) >= 2
    asyncio.run(run())


def test_demo_entry_point(capsys, monkeypatch):
    monkeypatch.setenv("PIVOT_PROFILE", "local")
    main(["--demo"])
    out = capsys.readouterr().out
    assert "pivot demo-1021:p63: confirmed" in out
    assert "push #4 pivot.confirmed" in out
