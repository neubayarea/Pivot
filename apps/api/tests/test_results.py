"""Ax10: a restart reads the AI's results back from PIVOT_DATA_DIR and makes no model call for them,
except for those that fell back to the template because the model failed: those are written again.
Every test runs on the files and on Cosmos DB (Ax11, an in-memory fake container)."""

import asyncio
import json
import os
from pathlib import Path

import pytest

from pivot_adapters import build_adapters
from pivot_adapters.azure import cosmos
from pivot_adapters.azure.fakes import FakeContainer
from pivot_api import sims
from pivot_api.personalize import Personalizer
from pivot_api.sims import SPECS, build_one, paths, store_one
from pivot_core.domain import ViewerPrefs
from pivot_worker.detect import DetectWorkflow
from pivot_worker.models import ModelReply, ModelUnavailable, OfflineModelClient, ScriptedModelClient
from pivot_worker.worker import Worker

SPEC = SPECS[0]
ZH = ViewerPrefs(language="zh")


class AnsweringModel:
    """A model that always answers: "yes, a pivot" from the Judge, a one-sentence card from the Explainer."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete_json(self, tier, messages, *, timeout):
        self.calls += 1
        request, _ = json.JSONDecoder().raw_decode(messages[-1]["content"])
        shown = [e["id"] for e in request["events"]]
        key = request.get("alarm", request.get("pivot"))["key_event_ids"]
        evidence = [i for i in key if i in shown][:1] or shown[:1]
        if tier == "mini":
            reply = {"is_pivot": True, "severity": 2, "trigger_event_ids": evidence, "reason": "momentum swung"}
        else:
            reply = {"headline": "The game turns here",
                     "sentences": [{"text": "The momentum swung after this moment.", "evidence_ids": evidence}]}
        return ModelReply(text=json.dumps(reply), model=f"answering-{tier}", tokens=10)


@pytest.fixture(scope="module")
def sim_output():
    from pivot_core.sim import build_demo_match, simulate
    return simulate(build_demo_match(SPEC.seed, SPEC.home_strength, SPEC.away_strength,
                                     SPEC.home_formation, SPEC.away_formation))


@pytest.fixture(params=["files", "cosmos"])
def backend(request, monkeypatch) -> FakeContainer | None:
    monkeypatch.setenv("PIVOT_RESULTS_BACKEND", request.param)
    if request.param == "files":
        return None
    container = FakeContainer()                                   # outlives every "process" of the test
    monkeypatch.setenv("PIVOT_COSMOS_ENDPOINT", "https://fake.documents.azure.com")
    monkeypatch.setattr(cosmos, "open_container", container.opener)
    return container


@pytest.fixture
def sim_dir(monkeypatch, sim_output, tmp_path, backend) -> Path:
    monkeypatch.setattr(sims, "simulate", lambda match: sim_output)
    return tmp_path / "sims"


async def start(sim_dir: Path, models, version: str = sims.SIM_VERSION):
    """One process start: store the match (reading back old results), then let the worker drain the queue."""
    adapters = build_adapters("local")
    build_one(SPEC, sim_dir, version)
    await store_one(adapters, paths(sim_dir, SPEC, version)[0])
    worker = Worker(adapters, DetectWorkflow(adapters.matches, models))
    while await worker.run_once(timeout=0.01):
        pass
    return adapters


def test_restart_serves_every_pivot_without_calling_the_model(sim_dir, backend):
    async def run():
        first = await start(sim_dir, AnsweringModel())
        pivots = await first.matches.list_pivots(SPEC.match_id)
        traces = await first.traces.list_traces(SPEC.match_id)
        assert pivots and traces and any(p.narrative and p.narrative.source == "llm" for p in pivots)
        confirmed = next(p for p in pivots if p.narrative is not None)
        writer = AnsweringModel()
        zh = await Personalizer(first.matches, writer).personalize(confirmed, ZH)
        assert zh.prefs == ZH and zh.pivot.narrative.source == "llm"

        models = ScriptedModelClient()                            # any call raises ModelUnavailable
        second = await start(sim_dir, models)
        assert models.calls == []
        if backend is not None:
            assert backend.calls["query"] == 2 and backend.calls["delete"] == 0   # one partition read per start
        assert await second.matches.list_pivots(SPEC.match_id) == pivots
        assert await second.traces.list_traces(SPEC.match_id) == traces
        assert await second.matches.get_narrative(SPEC.match_id, confirmed.pivot_id, ZH) == zh.pivot.narrative
    asyncio.run(run())


def test_fallbacks_from_a_failing_model_are_written_again_next_start(sim_dir):
    async def run():
        failing = ScriptedModelClient(mini=[ModelUnavailable("429")] * 50)
        first = await start(sim_dir, failing)
        assert failing.calls
        fallbacks = await first.matches.list_pivots(SPEC.match_id)
        assert fallbacks and all(p.status == "degraded" for p in fallbacks)

        working = AnsweringModel()
        second = await start(sim_dir, working)
        assert working.calls >= 2 * len(fallbacks)              # judge and explainer, for every one of them
        pivots = await second.matches.list_pivots(SPEC.match_id)
        assert [p.pivot_id for p in pivots] == [p.pivot_id for p in fallbacks]
        assert all(p.narrative.source == "llm" for p in pivots if p.status == "confirmed")
        assert any(p.status == "confirmed" for p in pivots)
        traces = await second.traces.list_traces(SPEC.match_id)
        assert {t.chain_id for t in traces} == {p.chain_id for p in pivots}   # no steps of the failed runs left

        third = await start(sim_dir, ScriptedModelClient())      # and those are kept from now on
        assert await third.matches.list_pivots(SPEC.match_id) == pivots
    asyncio.run(run())


def test_changed_sim_version_does_not_reuse_old_results(sim_dir, backend):
    async def run():
        await start(sim_dir, AnsweringModel(), "v1")
        models = AnsweringModel()
        second = await start(sim_dir, models, "v2")
        assert models.calls                                       # the worker wrote them again
        if backend is None:
            results = Path(os.environ["PIVOT_DATA_DIR"]) / "results" / SPEC.match_id
            assert [p.name for p in results.iterdir()] == ["v2"]
        else:
            assert {item["version"] for item in backend.items.values()} == {"v2"}
            assert not (Path(os.environ["PIVOT_DATA_DIR"]) / "results").exists()     # nothing on disk
        assert await second.matches.list_pivots(SPEC.match_id)
    asyncio.run(run())


def test_offline_model_results_are_not_kept(sim_dir):
    async def run():
        await start(sim_dir, OfflineModelClient())
        models = AnsweringModel()
        await start(sim_dir, models)
        assert models.calls
    asyncio.run(run())
