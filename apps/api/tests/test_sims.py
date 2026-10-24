import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from pivot_adapters import build_adapters
from pivot_api import sims
from pivot_api.app import app
from pivot_api.sims import SPECS, SimStatus, build_one, load_sims, paths, specs_from_env
from pivot_core.ports import PIVOT_CANDIDATES

SPEC = SPECS[0]


@pytest.fixture(scope="module")
def sim_output():
    """One real simulated match, shared: the tests count calls to simulate, not run it again."""
    from pivot_core.sim import build_demo_match, simulate
    return simulate(build_demo_match(SPEC.seed, SPEC.home_strength, SPEC.away_strength,
                                     SPEC.home_formation, SPEC.away_formation))


@pytest.fixture
def calls(monkeypatch, sim_output):
    counter = {"n": 0}

    def fake_simulate(match):
        counter["n"] += 1
        return sim_output

    monkeypatch.setattr(sims, "simulate", fake_simulate)
    return counter


def _load(adapters, data_dir, specs=(SPEC,)):
    status = SimStatus()
    with ThreadPoolExecutor(1) as pool:
        asyncio.run(load_sims(adapters, list(specs), data_dir, status, executor=pool))
    return status


def test_second_start_reads_the_cache(tmp_path, calls):
    status = _load(build_adapters("local"), tmp_path)
    assert calls["n"] == 1 and status.ready == [SPEC.match_id] and status.done
    data_path, frames_path = paths(tmp_path, SPEC)
    assert data_path.is_file() and frames_path.is_file()
    _load(build_adapters("local"), tmp_path)
    assert calls["n"] == 1


def test_new_sim_version_regenerates_and_drops_the_old_files(tmp_path, calls):
    assert build_one(SPEC, tmp_path, "v1")
    assert not build_one(SPEC, tmp_path, "v1")
    assert build_one(SPEC, tmp_path, "v2")
    assert calls["n"] == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == [f"{SPEC.match_id}.v2.frames.json.gz",
                                                          f"{SPEC.match_id}.v2.json.gz"]


def test_stored_match_and_candidates_on_the_queue(tmp_path, calls, sim_output):
    adapters = build_adapters("local")
    _load(adapters, tmp_path)

    async def check():
        match = await adapters.matches.get_match(SPEC.match_id)
        assert match.status == "finished" and match.score == sim_output.match.score
        assert len(await adapters.matches.list_events(SPEC.match_id)) == len(sim_output.events)
        assert len(await adapters.matches.list_metrics(SPEC.match_id)) > 90
        message = await adapters.queue.receive(PIVOT_CANDIDATES, timeout=0.1)
        assert message is not None and message.message_id.startswith(f"{SPEC.match_id}:")
        assert message.body["match_id"] == SPEC.match_id

    asyncio.run(check())


def test_specs_from_env(monkeypatch):
    monkeypatch.setenv("PIVOT_SIM_MATCHES", "2")
    assert [s.seed for s in specs_from_env()] == [101, 212]
    monkeypatch.setenv("PIVOT_SIM_MATCHES", "8")
    assert [s.seed for s in specs_from_env()][-2:] == [707, 808]
    monkeypatch.setenv("PIVOT_SIM_MATCHES", "0")
    assert specs_from_env() == []


def test_api_lists_simulated_matches_with_the_demo(tmp_path, monkeypatch, calls):
    monkeypatch.setenv("PIVOT_SIM_MATCHES", "1")
    monkeypatch.setenv("PIVOT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sims, "default_executor", lambda n: ThreadPoolExecutor(1))
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        for _ in range(500):
            if not client.get("/api/sims").json()["generating"]:
                break
            client.portal.call(asyncio.sleep, 0.02)
        assert client.get("/api/sims").json()["ready"] == 1
        ids = [m["match_id"] for m in client.get("/api/matches").json()]
        assert sorted(ids) == ["M-api-demo", "M-seed-101"]
        assert len(client.get("/api/matches/M-seed-101/timeline").json()) > 90
