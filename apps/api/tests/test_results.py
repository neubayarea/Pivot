"""Ax10: a restart reads the AI's results back from PIVOT_DATA_DIR and makes no model call for them."""

import asyncio
import os
from pathlib import Path

import pytest

from pivot_adapters import build_adapters
from pivot_api import sims
from pivot_api.personalize import Personalizer
from pivot_api.sims import SPECS, build_one, paths, store_one
from pivot_core.domain import ViewerPrefs
from pivot_worker.detect import DetectWorkflow
from pivot_worker.models import OfflineModelClient, ScriptedModelClient
from pivot_worker.worker import Worker

SPEC = SPECS[0]
ZH = ViewerPrefs(language="zh")


@pytest.fixture(scope="module")
def sim_output():
    from pivot_core.sim import build_demo_match, simulate
    return simulate(build_demo_match(SPEC.seed, SPEC.home_strength, SPEC.away_strength,
                                     SPEC.home_formation, SPEC.away_formation))


@pytest.fixture
def sim_dir(monkeypatch, sim_output, tmp_path) -> Path:
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


def test_restart_serves_every_pivot_without_calling_the_model(sim_dir):
    async def run():
        first = await start(sim_dir, OfflineModelClient())
        pivots = await first.matches.list_pivots(SPEC.match_id)
        traces = await first.traces.list_traces(SPEC.match_id)
        assert pivots and traces
        confirmed = next(p for p in pivots if p.narrative is not None)
        zh = await Personalizer(first.matches).personalize(confirmed, ZH)
        assert zh.prefs == ZH

        models = ScriptedModelClient()                            # any call raises ModelUnavailable
        second = await start(sim_dir, models)
        assert models.calls == []
        assert await second.matches.list_pivots(SPEC.match_id) == pivots
        assert await second.traces.list_traces(SPEC.match_id) == traces
        assert await second.matches.get_narrative(SPEC.match_id, confirmed.pivot_id, ZH) == zh.pivot.narrative
    asyncio.run(run())


def test_changed_sim_version_does_not_reuse_old_results(sim_dir):
    async def run():
        await start(sim_dir, OfflineModelClient(), "v1")
        models = ScriptedModelClient()
        second = await start(sim_dir, models, "v2")
        assert models.calls                                       # the worker wrote them again
        results = Path(os.environ["PIVOT_DATA_DIR"]) / "results" / SPEC.match_id
        assert [p.name for p in results.iterdir()] == ["v2"]
        assert await second.matches.list_pivots(SPEC.match_id)
    asyncio.run(run())
