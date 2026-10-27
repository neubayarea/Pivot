import asyncio

from pivot_adapters.local import InMemoryMatchRepository, InMemoryTraceRepository
from pivot_api.demo import DEMO_MATCH_ID, demo_match, demo_traces, seed_demo


def test_matches_upsert_and_most_recent_first():
    async def run():
        repo = InMemoryMatchRepository()
        first = demo_match()
        second = first.model_copy(update={"match_id": "m2"})
        await repo.upsert_match(first)
        await repo.upsert_match(second)
        assert [m.match_id for m in await repo.list_matches()] == ["m2", first.match_id]
        await repo.upsert_match(first.model_copy(update={"status": "finished"}))
        assert [m.match_id for m in await repo.list_matches()] == [first.match_id, "m2"]
        assert (await repo.get_match(first.match_id)).status == "finished"
        assert await repo.get_match("nope") is None
    asyncio.run(run())



def test_seeding_twice_changes_nothing():
    async def run():
        repo = InMemoryMatchRepository()
        await seed_demo(repo)
        before = len(await repo.list_events(DEMO_MATCH_ID))
        await seed_demo(repo)
        assert len(await repo.list_events(DEMO_MATCH_ID)) == before
        assert len(await repo.list_matches()) == 1
        assert len(await repo.list_pivots(DEMO_MATCH_ID)) == 2
    asyncio.run(run())


def test_seeding_traces_twice_changes_nothing():
    async def run():
        repo, traces = InMemoryMatchRepository(), InMemoryTraceRepository()
        await seed_demo(repo, traces)
        await seed_demo(repo, traces)
        assert len(await traces.list_traces(DEMO_MATCH_ID)) == len(demo_traces())
    asyncio.run(run())


def test_ax54_the_site_does_not_list_the_hand_made_sample(monkeypatch):
    from fastapi.testclient import TestClient

    from pivot_api.app import app

    monkeypatch.delenv("PIVOT_SAMPLE_MATCH")
    with TestClient(app) as client:
        assert DEMO_MATCH_ID not in [m["match_id"] for m in client.get("/api/matches").json()]
    monkeypatch.setenv("PIVOT_SAMPLE_MATCH", "1")
    with TestClient(app) as client:
        assert DEMO_MATCH_ID in [m["match_id"] for m in client.get("/api/matches").json()]
