import asyncio

from pivot_adapters.local import InMemoryMatchRepository, InMemoryTraceRepository


def test_events_dedup_by_seq_and_since(make_event):
    async def run():
        repo = InMemoryMatchRepository()
        assert await repo.append_events([make_event(2), make_event(1), make_event(3, match_id="m2")]) == 3
        assert await repo.append_events([make_event(2), make_event(4)]) == 1
        assert [e.seq for e in await repo.list_events("m1")] == [1, 2, 4]
        assert [e.seq for e in await repo.list_events("m1", since_seq=2)] == [4]
        assert await repo.list_events("nope") == []
    asyncio.run(run())


def test_pivots_upsert_and_order(make_pivot):
    async def run():
        repo = InMemoryMatchRepository()
        await repo.upsert_pivot(make_pivot(70))
        await repo.upsert_pivot(make_pivot(55))
        await repo.upsert_pivot(make_pivot(70, status="confirmed"))
        assert [(p.minute, p.status) for p in await repo.list_pivots("m1")] == [(55, "pending"), (70, "confirmed")]
        assert (await repo.get_pivot("m1", "m1:p55")).minute == 55
        assert await repo.get_pivot("m1", "m1:p99") is None
    asyncio.run(run())


def test_stored_copies_are_isolated(make_event):
    async def run():
        repo = InMemoryMatchRepository()
        event = make_event(1)
        await repo.append_events([event])
        event.meta["x"] = "changed"
        (await repo.list_events("m1"))[0].meta["y"] = "changed"
        assert (await repo.list_events("m1"))[0].meta == {}
    asyncio.run(run())


def test_traces_by_match_and_chain(make_trace):
    async def run():
        repo = InMemoryTraceRepository()
        for trace in [make_trace("c2", 0), make_trace("c1", 1), make_trace("c1", 0), make_trace("c9", 0, "m2")]:
            await repo.append_trace(trace)
        assert [t.trace_id for t in await repo.list_traces("m1")] == ["c1:0", "c1:1", "c2:0"]
        assert [t.trace_id for t in await repo.list_traces("m1", chain_id="c2")] == ["c2:0"]
    asyncio.run(run())
