"""Ax11: the AI's results in Cosmos DB behave like the files (Ax10), and the site falls back to the files."""

import asyncio
import inspect
import os

import pytest

from pivot_adapters import build_adapters
from pivot_adapters.azure import cosmos
from pivot_adapters.azure.cosmos import CosmosResults
from pivot_adapters.azure.fakes import FakeContainer
from pivot_adapters.local import FileResults, ResultFiles, ResultStore
from pivot_core.domain import AgentTrace, ExplanationSentence, Narrative, ViewerPrefs

ZH = ViewerPrefs(language="zh", audience="fan")


def narrative(prefs: ViewerPrefs, source: str = "llm", chain_id: str = "c55") -> Narrative:
    return Narrative(prefs=prefs, headline=f"{prefs.language} headline", source=source,
                     sentences=[ExplanationSentence(text="Away took over.", evidence_ids=["m1-s00010"])],
                     chain_id=chain_id)


def store(container: FakeContainer, tag: str = "") -> ResultStore:
    return ResultStore(CosmosResults("https://fake.documents.azure.com", opener=container.opener), tag)


async def write_some(results: ResultStore, make_pivot, make_trace) -> None:
    await results.open_match("m1", "v1")
    await results.matches.upsert_pivot(make_pivot(55, "confirmed"))
    await results.matches.upsert_pivot(make_pivot(70, "rejected"))
    await results.matches.upsert_narrative("m1", "m1:p55", narrative(ZH))
    for step in range(3):
        await results.traces.append_trace(make_trace("c55", step).model_copy(update={"input_ref": "m1:p55"}))


def test_store_then_reload_gives_the_same_results(make_pivot, make_trace):
    async def run():
        container = FakeContainer()
        first = store(container)
        await write_some(first, make_pivot, make_trace)
        assert container.calls["upsert"] == 6 and len(container.items) == 6
        assert {pk for pk, _ in container.items} == {"m1"}

        second = store(container)
        assert await second.open_match("m1", "v1") == 2
        assert container.calls["query"] == 2 and container.calls["delete"] == 0   # one query per opened match
        assert await second.matches.list_pivots("m1") == await first.matches.list_pivots("m1")
        assert await second.matches.get_narrative("m1", "m1:p55", ZH) == narrative(ZH)
        assert await second.traces.list_traces("m1") == await first.traces.list_traces("m1")
        assert second.backend.request_charge == 1
    asyncio.run(run())


def test_new_version_or_tag_starts_empty_and_drops_the_old_one(make_pivot, make_trace):
    async def run():
        container = FakeContainer()
        await write_some(store(container), make_pivot, make_trace)
        assert await store(container, tag="again").open_match("m1", "v1") == 0
        assert container.items == {}
        await write_some(store(container), make_pivot, make_trace)
        second = store(container)
        assert await second.open_match("m1", "v2") == 0
        assert await second.traces.list_traces("m1") == []
        assert container.items == {}
    asyncio.run(run())


def test_unopened_matches_are_not_written(make_pivot):
    async def run():
        container = FakeContainer()
        results = store(container)
        await results.matches.upsert_pivot(make_pivot(55, "confirmed"))
        assert await results.matches.get_pivot("m1", "m1:p55") is not None
        assert container.calls["upsert"] == 0
    asyncio.run(run())


def chain(pivot_id: str, chain_id: str, *steps: tuple[str, str]) -> list[AgentTrace]:
    return [AgentTrace(trace_id=f"{chain_id}:{i}", chain_id=chain_id, step=i, match_id="m1", agent=agent,
                       input_ref=pivot_id, output_summary=agent, latency_ms=1, status=status)
            for i, (agent, status) in enumerate(steps)]


def test_fallbacks_are_dropped_and_deleted(make_pivot):
    async def run():
        container = FakeContainer()
        first = store(container)
        await first.open_match("m1", "v1")
        for minute, steps in {40: [("judge", "degraded"), ("template", "degraded")],
                              70: [("judge", "rejected")]}.items():
            pivot = make_pivot(minute, "rejected" if minute == 70 else "degraded")
            for trace in chain(pivot.pivot_id, pivot.chain_id, *steps):
                await first.traces.append_trace(trace)
            await first.matches.upsert_pivot(pivot)
            await first.matches.upsert_narrative("m1", pivot.pivot_id, narrative(ZH, chain_id=pivot.chain_id))
        await first.matches.upsert_narrative("m1", "m1:p70", narrative(ViewerPrefs(language="es"), "template"))
        assert len(container.items) == 2 + 3 + 2                     # the template version is never written

        second = store(container)
        assert await second.open_match("m1", "v1") == 1
        assert [p.minute for p in await second.matches.list_pivots("m1")] == [70]
        assert await second.matches.get_narrative("m1", "m1:p40", ZH) is None
        assert len(container.items) == 1 + 1 + 1                     # p40 and its chain and narrative are gone
    asyncio.run(run())


def test_unreachable_cosmos_falls_back_to_the_files(tmp_path, make_pivot, caplog):
    async def unreachable(endpoint, database):
        raise ConnectionError("cannot reach pivot-cosmos")

    async def run():
        results = ResultStore(CosmosResults("https://x.documents.azure.com", opener=unreachable),
                              fallback=FileResults(tmp_path))
        assert await results.open_match("m1", "v1") == 0
        await results.matches.upsert_pivot(make_pivot(55, "confirmed"))
        assert isinstance(results.backend, FileResults)
        assert (tmp_path / "m1" / "v1" / "pivots" / "m1%3Ap55.json").exists()
        assert "keeping the AI's results on disk" in caplog.text
        missing = ResultStore(CosmosResults(""), fallback=FileResults(tmp_path))   # no endpoint set
        assert await missing.open_match("m1", "v1") == 1
    asyncio.run(run())


def test_compose_picks_the_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("PIVOT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PIVOT_RESULTS", raising=False)
    monkeypatch.delenv("PIVOT_RESULTS_BACKEND", raising=False)
    assert isinstance(build_adapters("local").results, ResultFiles)
    monkeypatch.setenv("PIVOT_RESULTS_BACKEND", "cosmos")
    monkeypatch.setenv("PIVOT_COSMOS_ENDPOINT", "https://pivot-cosmos.documents.azure.com:443/")
    monkeypatch.delenv("PIVOT_COSMOS_DATABASE", raising=False)
    results = build_adapters("local").results
    assert isinstance(results.backend, CosmosResults) and results.backend.database == "pivot"
    monkeypatch.setenv("PIVOT_RESULTS_BACKEND", "blob")
    with pytest.raises(ValueError):
        build_adapters("local")


@pytest.mark.skipif(os.getenv("PIVOT_COSMOS_IT") != "1", reason="needs the real Cosmos account: PIVOT_COSMOS_IT=1")
def test_real_account_round_trip(make_pivot):
    """Writes one pivot under a throwaway match id in the real account, reads it back, then removes it."""
    async def run():
        endpoint = os.getenv("PIVOT_COSMOS_ENDPOINT", "https://pivot-cosmos.documents.azure.com:443/")
        pivot = make_pivot(55, "confirmed", match_id="it-ax11")
        first = ResultStore(CosmosResults(endpoint), tag="it")
        try:
            await first.open_match("it-ax11", "v1")
            await first.matches.upsert_pivot(pivot)
        finally:
            await first.close()
        second = ResultStore(CosmosResults(endpoint), tag="it")
        try:
            assert await second.open_match("it-ax11", "v1") == 1
            assert await second.matches.get_pivot("it-ax11", pivot.pivot_id) == pivot
            await second.backend.load("it-ax11", "gone")              # deletes the other versions: ours
            assert await second.backend.load("it-ax11", "v1-it") == {"pivots": [], "narratives": [], "traces": []}
        finally:
            await second.close()
    asyncio.run(run())


def test_container_uses_the_shared_throughput():
    assert "offer_throughput" not in inspect.getsource(cosmos)    # a throughput of its own costs money


def test_what_if_scenarios_and_their_traces_are_kept(make_trace):
    from pivot_core.domain import OutcomeDist, Scenario, ScenarioSpec, SimResult

    even = OutcomeDist(home_win=.4, draw=.3, away_win=.3,
                       ci95={"home_win": (.3, .5), "draw": (.2, .4), "away_win": (.2, .4)})
    scenario = Scenario(
        scenario_id="m1:sabc", match_id="m1", status="completed", done=400,
        spec=ScenarioSpec(type="remove_goal", pivot_id="m1:p55", target_event_id="e1", at_minute=55, seed_base=7),
        result=SimResult(scenario_id="m1:sabc", baseline=even, counterfactual=even, significant={},
                         narrative=narrative(ViewerPrefs(), source="template"), runtime_ms=1, executor="local_pool"))

    async def run():
        container = FakeContainer()
        first = store(container)
        await first.store_scenario("m1", "k1", scenario)            # not opened yet: not written
        assert container.items == {} and first.scenarios("m1") == {}
        await first.open_match("m1", "v1")
        await first.store_scenario("m1", "k1", scenario)
        await first.traces.append_trace(make_trace("whatif:m1:sabc:x", 0).model_copy(update={"input_ref": "m1:sabc"}))
        await first.traces.append_trace(make_trace("whatif:m1:sgone:x", 0).model_copy(update={"input_ref": "m1:sgone"}))

        second = store(container)
        await second.open_match("m1", "v1")
        assert second.scenarios("m1") == {"k1": scenario}           # a template comparison is kept too
        assert [t.input_ref for t in await second.traces.list_traces("m1")] == ["m1:sabc"]
    asyncio.run(run())
