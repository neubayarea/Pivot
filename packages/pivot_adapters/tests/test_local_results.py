"""Ax10: the AI's results of an opened match are written to disk and read back by the next process."""

import asyncio
import json

from pivot_adapters import build_adapters
from pivot_adapters.local import InMemoryMatchRepository, ResultFiles
from pivot_core.domain import AgentTrace, ExplanationSentence, Narrative, Verdict, ViewerPrefs

ZH = ViewerPrefs(language="zh", audience="fan")


def narrative(prefs: ViewerPrefs, chain_id: str = "c55") -> Narrative:
    return Narrative(prefs=prefs, headline=f"{prefs.language} headline", source="llm",
                     sentences=[ExplanationSentence(text="Away took over.", evidence_ids=["m1-s00010"])],
                     chain_id=chain_id)


async def write_some(files: ResultFiles, make_pivot, make_trace) -> None:
    await files.open_match("m1", "v1")
    await files.matches.upsert_pivot(make_pivot(55, "confirmed"))
    await files.matches.upsert_pivot(make_pivot(70, "rejected"))
    await files.matches.upsert_narrative("m1", "m1:p55", narrative(ZH))
    for step in range(3):
        await files.traces.append_trace(make_trace("c55", step).model_copy(update={"input_ref": "m1:p55"}))


def test_store_then_reload_gives_the_same_results(tmp_path, make_pivot, make_trace):
    async def run():
        first = ResultFiles(tmp_path)
        await write_some(first, make_pivot, make_trace)

        second = ResultFiles(tmp_path)
        assert await second.matches.list_pivots("m1") == []
        assert await second.open_match("m1", "v1") == 2
        assert await second.matches.list_pivots("m1") == await first.matches.list_pivots("m1")
        assert await second.matches.get_narrative("m1", "m1:p55", ZH) == narrative(ZH)
        assert await second.traces.list_traces("m1") == await first.traces.list_traces("m1")
    asyncio.run(run())


def test_new_version_starts_empty_and_drops_the_old_one(tmp_path, make_pivot, make_trace):
    async def run():
        await write_some(ResultFiles(tmp_path), make_pivot, make_trace)
        second = ResultFiles(tmp_path)
        assert await second.open_match("m1", "v2") == 0
        assert await second.matches.list_pivots("m1") == []
        assert await second.traces.list_traces("m1") == []
        assert not (tmp_path / "m1" / "v1").exists()
    asyncio.run(run())


def test_tag_is_part_of_the_version(tmp_path, make_pivot, make_trace):
    async def run():
        await write_some(ResultFiles(tmp_path), make_pivot, make_trace)
        assert await ResultFiles(tmp_path, tag="again").open_match("m1", "v1") == 0
    asyncio.run(run())


def test_corrupt_files_are_skipped(tmp_path, make_pivot, make_trace):
    async def run():
        await write_some(ResultFiles(tmp_path), make_pivot, make_trace)
        pivots = tmp_path / "m1" / "v1" / "pivots"
        (pivots / "m1%3Ap55.json").write_text("{not json", encoding="utf-8")
        (pivots / "extra.json").write_text(json.dumps({"pivot_id": "x"}), encoding="utf-8")
        second = ResultFiles(tmp_path)
        assert await second.open_match("m1", "v1") == 1
        assert [p.pivot_id for p in await second.matches.list_pivots("m1")] == ["m1:p70"]
        assert await second.traces.list_traces("m1") == []         # p55's chain: its pivot is written again
    asyncio.run(run())


def test_unopened_matches_stay_in_memory(tmp_path, make_pivot):
    async def run():
        files = ResultFiles(tmp_path)
        await files.matches.upsert_pivot(make_pivot(55, "confirmed"))
        assert await files.matches.get_pivot("m1", "m1:p55") is not None
        assert not tmp_path.exists() or not any(tmp_path.iterdir())
    asyncio.run(run())


def test_compose_uses_the_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("PIVOT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PIVOT_RESULTS", raising=False)
    adapters = build_adapters("local")
    assert isinstance(adapters.results, ResultFiles) and adapters.results.root == tmp_path / "results"
    assert adapters.matches is adapters.results.matches and adapters.traces is adapters.results.traces
    monkeypatch.setenv("PIVOT_RESULTS", "0")
    adapters = build_adapters("local")
    assert adapters.results is None and type(adapters.matches) is InMemoryMatchRepository


def chain(pivot_id: str, chain_id: str, *steps: tuple[str, str]) -> list[AgentTrace]:
    return [AgentTrace(trace_id=f"{chain_id}:{i}", chain_id=chain_id, step=i, match_id="m1", agent=agent,
                       input_ref=pivot_id, output_summary=agent, latency_ms=1, status=status,
                       verdict=Verdict(passed=False) if agent == "verifier" and status == "rejected" else None)
            for i, (agent, status) in enumerate(steps)]


def test_fallbacks_from_failed_calls_are_dropped_and_written_again(tmp_path, make_pivot):
    """Template text because the model failed is not served again; template text the Verifier forced is."""
    failed = {   # minute -> the chain that ended in the template because something failed
        40: [("judge", "degraded"), ("template", "degraded")],                         # judge 429
        50: [("judge", "ok"), ("explainer", "error"), ("template", "degraded")],      # explainer timeout
        60: [("judge", "ok"), ("explainer", "ok"), ("verifier", "error"), ("template", "degraded")],
        65: [("template", "degraded")],                                               # the workflow failed
    }
    kept = {
        55: [("judge", "ok"), ("explainer", "ok"), ("verifier", "rejected"), ("explainer", "retried"),
             ("verifier", "rejected"), ("template", "degraded")],                     # drafts did not pass
        70: [("judge", "rejected")],                                                  # the model said no
    }

    async def run():
        files = ResultFiles(tmp_path)
        await files.open_match("m1", "v1")
        for minute, steps in {**failed, **kept}.items():
            pivot = make_pivot(minute, "rejected" if minute == 70 else "degraded")
            for trace in chain(pivot.pivot_id, pivot.chain_id, *steps):
                await files.traces.append_trace(trace)
            await files.matches.upsert_pivot(pivot)
            await files.matches.upsert_narrative("m1", pivot.pivot_id, narrative(ZH, pivot.chain_id))
        await files.matches.upsert_narrative("m1", "m1:p55", narrative(ViewerPrefs(language="es")).model_copy(
            update={"source": "template"}))                                         # never written

        second = ResultFiles(tmp_path)
        assert await second.open_match("m1", "v1") == 2
        assert [p.minute for p in await second.matches.list_pivots("m1")] == [55, 70]
        assert {t.input_ref for t in await second.traces.list_traces("m1")} == {"m1:p55", "m1:p70"}
        assert await second.matches.get_narrative("m1", "m1:p55", ZH) is not None
        assert await second.matches.get_narrative("m1", "m1:p40", ZH) is None
        assert await second.matches.get_narrative("m1", "m1:p55", ViewerPrefs(language="es")) is None
        # their files are gone too, so a retry that reuses a chain id starts clean
        folder = tmp_path / "m1" / "v1"
        assert len(list((folder / "pivots").iterdir())) == 2
        assert len(list((folder / "traces").iterdir())) == len(kept[55]) + len(kept[70])
        assert len(list((folder / "narratives").iterdir())) == 2
    asyncio.run(run())
