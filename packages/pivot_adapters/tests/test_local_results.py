"""Ax10: the AI's results of an opened match are written to disk and read back by the next process."""

import asyncio
import json

from pivot_adapters import build_adapters
from pivot_adapters.local import InMemoryMatchRepository, ResultFiles
from pivot_core.domain import ExplanationSentence, Narrative, ViewerPrefs

ZH = ViewerPrefs(language="zh", audience="fan")


def narrative(prefs: ViewerPrefs, chain_id: str = "c55") -> Narrative:
    return Narrative(prefs=prefs, headline=f"{prefs.language} headline", source="template",
                     sentences=[ExplanationSentence(text="Away took over.", evidence_ids=["m1-s00010"])],
                     chain_id=chain_id)


async def write_some(files: ResultFiles, make_pivot, make_trace) -> None:
    await files.open_match("m1", "v1")
    await files.matches.upsert_pivot(make_pivot(55, "confirmed"))
    await files.matches.upsert_pivot(make_pivot(70, "rejected"))
    await files.matches.upsert_narrative("m1", "m1:p55", narrative(ZH))
    for step in range(3):
        await files.traces.append_trace(make_trace("detect:m1:55:d1", step))


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
        assert len(await second.traces.list_traces("m1")) == 3
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
