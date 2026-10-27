"""Bx11: the recorded demo's What-ifs, run ahead of time by scripts/make_whatif_fixture.py, are served from
eval/fixtures/demo-1021.whatif.json without replaying, and only for the demo they were run on."""

import asyncio
import json
import shutil

import pytest

from pivot_adapters import build_adapters
from pivot_api import sims
from pivot_api.sims import Replay
from pivot_api.whatif import WhatIf, cache_key, load_precomputed, precomputed_path
from pivot_core.sim.whatif import run_whatif
from pivot_worker.models import OfflineModelClient
from pivot_worker.pipeline import FakePipeline
from pivot_worker.worker import Worker

FILE = precomputed_path(sims.FIXTURE)


class NoReplays:
    """A runner that must not be called."""

    def __init__(self) -> None:
        self.calls = []

    def __call__(self, match, spec, **_):
        self.calls.append(spec)
        raise AssertionError(f"replayed {spec.pivot_id} {spec.type}")


@pytest.fixture(autouse=True)
def in_memory(monkeypatch):
    monkeypatch.setenv("PIVOT_RESULTS", "0")


async def demo(fixture=sims.FIXTURE):
    """The demo as the server stores it, with the pivots the worker's fake pipeline gives it."""
    adapters = build_adapters("local")
    replays: dict[str, Replay] = {}
    match_id, _ = await sims.load_fixture(adapters, fixture, replays)
    worker = Worker(adapters, FakePipeline())
    while await worker.run_once(timeout=0.1):
        pass
    return adapters, replays, match_id


async def until_done(whatif: WhatIf, scenario_ids, timeout=30.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while any(whatif.get(s).status not in ("completed", "failed") for s in scenario_ids):
        assert loop.time() < deadline, "scenarios still running"
        await asyncio.sleep(0.02)
    return [whatif.get(s) for s in scenario_ids]


def stored():
    data = json.loads(FILE.read_bytes())
    return data, load_precomputed(FILE, data["version"])


def test_the_file_is_for_this_demo_and_keyed_as_the_server_keys():
    data, scenarios = stored()
    _, replays, match_id = asyncio.run(demo())
    assert data["match_id"] == match_id and data["version"] == replays[match_id].version   # re-run the script
    assert scenarios and all(key == cache_key(data["version"], s.spec) for key, s in scenarios.items())
    assert all(s.status == "completed" and s.result.baseline_stats is not None
               and s.result.narrative is not None for s in scenarios.values())


def test_every_chip_is_served_from_the_file_without_a_replay():
    _, scenarios = stored()
    sizes = sorted({s.spec.n_runs for s in scenarios.values()})

    async def ask_all():
        adapters, replays, match_id = await demo()
        runner = NoReplays()
        whatif = WhatIf(adapters, replays, OfflineModelClient(), runner=runner, workers=0)
        whatif.precomputed[match_id] = load_precomputed(FILE, replays[match_id].version)
        whatif.start()
        try:
            match, asked = await adapters.matches.get_match(match_id), []
            for pivot in await adapters.matches.list_pivots(match_id):
                for option in [o for o in await whatif.options(pivot, match) if o.enabled]:
                    for n_runs in sizes:
                        asked.append((await whatif.submit(pivot.pivot_id, option.type, n_runs)).scenario_id)
            return runner, await until_done(whatif, asked)
        finally:
            await whatif.stop()

    runner, served = asyncio.run(ask_all())
    assert runner.calls == []
    assert len(served) == len(scenarios)                      # every chip at every size is in the file
    by_id = {s.scenario_id: s for s in scenarios.values()}
    for scenario in served:
        assert scenario.status == "completed"
        before = by_id[scenario.scenario_id].result
        assert scenario.result.model_copy(update={"narrative": None}) == before.model_copy(update={"narrative": None})
        assert scenario.result.narrative.source == "template"   # no model here: the template, written again


def test_the_warm_up_replays_only_chips_not_in_the_file():
    async def warm():
        adapters, replays, match_id = await demo()
        runner = NoReplays()
        whatif = WhatIf(adapters, replays, OfflineModelClient(), runner=runner, workers=0)
        whatif.precomputed[match_id] = load_precomputed(FILE, replays[match_id].version)
        whatif.start()
        try:
            await whatif.warm(match_id, 2, wait=1)
            return runner, await until_done(whatif, list(whatif.scenarios))
        finally:
            await whatif.stop()

    runner, scenarios = asyncio.run(warm())
    assert runner.calls == [] and len(scenarios) == 15        # all five chips of each pivot, comparisons only
    assert all(s.status == "completed" for s in scenarios)


def test_a_changed_demo_does_not_use_the_file(tmp_path):
    demo_file = tmp_path / sims.FIXTURE.name
    demo_file.write_bytes(sims.FIXTURE.read_bytes() + b"\n")                  # same match, another hash
    shutil.copy(FILE, precomputed_path(demo_file))

    async def ask():
        adapters, replays, match_id = await demo(demo_file)
        version = replays[match_id].version
        calls = []

        def runner(match, spec, **_):
            calls.append(spec)
            raise RuntimeError("replayed")

        whatif = WhatIf(adapters, replays, OfflineModelClient(), runner=runner, workers=0)
        whatif.precomputed[match_id] = load_precomputed(precomputed_path(demo_file), version)
        whatif.start()
        try:
            scenario = await whatif.submit(f"{match_id}:p79", "remove_goal")
            await until_done(whatif, [scenario.scenario_id])
        finally:
            await whatif.stop()
        return whatif.precomputed[match_id], calls

    precomputed, calls = asyncio.run(ask())
    assert precomputed == {} and len(calls) == 1             # replayed, not served from the stale file


def test_a_stored_result_equals_a_fresh_run():
    """The cheapest chip (the 90' goal, from the 79' pivot) replayed here: same numbers as in the file."""
    _, scenarios = stored()
    ahead = next(s for s in scenarios.values()
                 if s.spec.pivot_id.endswith(":p79") and s.spec.type == "remove_goal" and s.spec.n_runs == 200)

    async def fresh():
        adapters, replays, match_id = await demo()
        replay = replays[match_id]
        return await asyncio.to_thread(run_whatif, replay.build(), ahead.spec, seed=replay.seed, plants=replay.plants,
                                       workers=2, scenario_id=ahead.scenario_id)

    result = asyncio.run(fresh())
    keep = {"narrative": None, "runtime_ms": 0}
    assert result.model_copy(update=keep) == ahead.result.model_copy(update=keep)
