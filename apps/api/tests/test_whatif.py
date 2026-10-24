"""What-if API (A09): chips, POST -> poll -> completed with a narrative, errors, cache and read-back."""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from pivot_adapters import build_adapters
from pivot_api import sims
from pivot_api.app import app
from pivot_api.demo import DEMO_MATCH_ID, demo_match
from pivot_api.sims import Replay
from pivot_api.whatif import NOT_REPLAYABLE, WhatIf, cache_key, seed_base
from pivot_core.domain import OutcomeDist, Pivot, ScenarioSpec, SimResult
from pivot_core.sim.whatif import run_whatif
from pivot_worker.models import OfflineModelClient

PIVOT_ID = f"{DEMO_MATCH_ID}:p61"
CHIP_FIELDS = {"type", "label", "enabled", "disabled_reason", "target_event_id", "at_minute", "team", "params"}


def dist(home: float, draw: float) -> OutcomeDist:
    away = round(1 - home - draw, 6)
    return OutcomeDist(home_win=home, draw=draw, away_win=away,
                       ci95={"home_win": (home - .05, home + .05), "draw": (draw - .05, draw + .05),
                             "away_win": (max(0, away - .05), away + .05)})


class FakeRunner:
    """Stands in for run_whatif: reports progress in two steps and returns a fixed result."""

    def __init__(self) -> None:
        self.calls = []

    def __call__(self, match, spec, *, seed, plants, progress, pool, workers, scenario_id, n_runs):
        self.calls.append(spec)
        total = 2 * n_runs
        progress(total // 2, total)
        progress(total, total)
        return SimResult(scenario_id=scenario_id, baseline=dist(.2, .3), counterfactual=dist(.6, .2),
                         significant={"home_win": True, "draw": False, "away_win": True}, runtime_ms=5,
                         executor="local_pool")


@pytest.fixture
def runner():
    return FakeRunner()


@pytest.fixture
def client(monkeypatch, runner):
    monkeypatch.delenv("PIVOT_PROFILE", raising=False)
    monkeypatch.delenv("PIVOT_DEMO", raising=False)
    monkeypatch.delenv("PIVOT_FOUNDRY_ENDPOINT", raising=False)     # offline: the template writes the comparison
    with TestClient(app) as client:
        whatif: WhatIf = app.state.whatif
        whatif.runner, whatif.workers = runner, 0
        whatif.replays[DEMO_MATCH_ID] = Replay("v1", demo_match)
        yield client


def wait_done(client, scenario_id, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        scenario = client.get(f"/api/scenarios/{scenario_id}").json()
        if scenario["status"] in ("completed", "failed"):
            return scenario
        time.sleep(0.05)
    raise AssertionError(f"{scenario_id} still {scenario['status']}")


def test_chips_of_a_known_pivot(client):
    chips = client.get(f"/api/pivots/{PIVOT_ID}/scenarios").json()
    assert [set(c) for c in chips] == [CHIP_FIELDS] * 5
    by_type = {c["type"]: c for c in chips}
    sub = by_type["cancel_substitution"]
    assert sub["enabled"] and sub["label"] == "Cancel 62′ substitution" and sub["at_minute"] == 61
    assert by_type["move_substitution"]["params"] == {"new_minute": 74}
    red = by_type["remove_red_card"]
    assert not red["enabled"] and red["disabled_reason"] == "No red card in this match"
    assert chips[0]["type"] == "cancel_substitution"            # the pivot's own trigger first


def test_a_match_without_a_replay_has_only_disabled_chips(client):
    del app.state.whatif.replays[DEMO_MATCH_ID]
    chips = client.get(f"/api/pivots/{PIVOT_ID}/scenarios").json()
    assert {(c["enabled"], c["disabled_reason"]) for c in chips} == {(False, NOT_REPLAYABLE)}
    assert client.post("/api/scenarios", json={"pivot_id": PIVOT_ID, "type": "cancel_substitution"}).status_code == 422


def test_post_then_poll_until_completed_with_a_narrative(client, runner):
    response = client.post("/api/scenarios", json={"pivot_id": PIVOT_ID, "type": "cancel_substitution"})
    assert response.status_code == 202
    queued = response.json()
    assert queued["status"] == "queued" and queued["done"] == 0 and queued["result"] is None
    assert queued["scenario_id"].startswith(f"{DEMO_MATCH_ID}:s")
    spec = queued["spec"]
    assert (spec["n_runs"], spec["at_minute"], spec["seed_base"]) == (200, 61, seed_base(PIVOT_ID, "cancel_substitution"))

    done = wait_done(client, queued["scenario_id"])
    assert done["status"] == "completed" and done["done"] == 400
    assert done["result"]["counterfactual"]["home_win"] == 0.6
    narrative = done["result"]["narrative"]
    assert narrative["source"] == "template" and narrative["sentences"]

    traces = [t for t in client.get(f"/api/matches/{DEMO_MATCH_ID}/traces").json()
              if t["input_ref"] == queued["scenario_id"]]
    assert [t["agent"] for t in traces] == ["executor", "comparator", "template"]
    assert len({t["chain_id"] for t in traces}) == 1 and traces[0]["chain_id"].startswith("whatif:")


def test_progress_and_end_are_pushed_on_the_match_channel(client):
    with client.websocket_connect(f"/api/ws/matches/{DEMO_MATCH_ID}") as ws:
        scenario = client.post("/api/scenarios", json={"pivot_id": PIVOT_ID, "type": "remove_goal"}).json()
        seen = []
        while not seen or seen[-1]["type"] != "scenario.completed":
            envelope = ws.receive_json()
            if envelope["type"].startswith("scenario."):
                seen.append(envelope)
    assert all(e["payload"]["scenario_id"] == scenario["scenario_id"] and e["payload"]["total"] == 400 for e in seen)
    assert [e["payload"]["done"] for e in seen] == [0, 200, 400, 400]
    assert seen[-1]["payload"]["result"]["narrative"] is not None


def test_same_question_twice_is_answered_from_the_cache(client, runner):
    body = {"pivot_id": PIVOT_ID, "type": "move_substitution", "params": {"new_minute": 70}}
    first = client.post("/api/scenarios", json=body).json()
    wait_done(client, first["scenario_id"])
    again = client.post("/api/scenarios", json=body)
    assert again.status_code == 202
    assert again.json()["scenario_id"] == first["scenario_id"] and again.json()["status"] == "completed"
    assert len(runner.calls) == 1
    assert runner.calls[0].params == {"new_minute": 70} and runner.calls[0].at_minute == 61
    # Another number of runs is another question.
    other = client.post("/api/scenarios", json={**body, "n_runs": 500}).json()
    assert other["scenario_id"] != first["scenario_id"]


def test_warm_up_runs_the_first_chips_after_what_viewers_ask(client, runner):
    pivots = [p for p in client.get(f"/api/matches/{DEMO_MATCH_ID}/pivots").json() if p["status"] != "rejected"]
    whatif: WhatIf = app.state.whatif

    async def resume():
        whatif.start()

    client.portal.call(whatif.stop)                                  # queue everything first, then run
    client.portal.call(whatif.warm, DEMO_MATCH_ID, 1, 0)
    asked = client.post("/api/scenarios", json={"pivot_id": PIVOT_ID, "type": "remove_goal"}).json()
    client.portal.call(resume)
    wait_done(client, asked["scenario_id"])
    deadline = time.monotonic() + 10
    while len(runner.calls) < len(pivots) + 1 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert runner.calls[0].type == "remove_goal"                    # the viewer's question went first
    assert sorted(s.pivot_id for s in runner.calls[1:]) == sorted(p["pivot_id"] for p in pivots)


def test_errors(client):
    post = lambda **body: client.post("/api/scenarios", json={"pivot_id": PIVOT_ID, **body})   # noqa: E731
    assert client.get("/api/pivots/nope:p1/scenarios").status_code == 404
    assert client.post("/api/scenarios", json={"pivot_id": "nope:p1", "type": "remove_goal"}).status_code == 404
    assert post(type="remove_red_card").status_code == 422              # disabled: no red card
    assert post(type="not_a_type").status_code == 422
    assert post(type="remove_goal", n_runs=300).status_code == 422
    assert post(type="remove_goal", params={"new_minute": 70}).status_code == 422
    assert post(type="move_substitution", params={"new_minute": 20}).status_code == 422
    assert client.get(f"/api/scenarios/{DEMO_MATCH_ID}:snope").status_code == 404


def test_cache_key_depends_on_version_params_and_runs():
    a = ScenarioSpec(type="move_substitution", pivot_id=PIVOT_ID, target_event_id="e1", at_minute=61,
                     params={"new_minute": 74}, n_runs=200, seed_base=seed_base(PIVOT_ID, "move_substitution"))
    assert cache_key("v1", a) == cache_key("v1", a.model_copy())
    assert cache_key("v2", a) != cache_key("v1", a)
    assert cache_key("v1", a.model_copy(update={"n_runs": 500})) != cache_key("v1", a)
    assert cache_key("v1", a.model_copy(update={"params": {"new_minute": 60}})) != cache_key("v1", a)
    assert seed_base(PIVOT_ID, "remove_goal") != a.seed_base


# --- the recorded demo, replayed for real, and kept across a restart -------------------------

def test_recorded_demo_replays_for_real_and_is_read_back_after_a_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("PIVOT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PIVOT_RESULTS_BACKEND", raising=False)

    async def start():
        adapters = build_adapters("local")
        replays: dict[str, Replay] = {}
        match_id, _ = await sims.load_fixture(adapters, sims.FIXTURE, replays)
        return adapters, replays, match_id

    async def first_run():
        adapters, replays, match_id = await start()
        events = await adapters.matches.list_events(match_id)
        sub = next(e for e in events if e.type == "substitution" and e.minute >= 60)
        # The worker writes the fixture's pivots; here one is stored by hand on its 63' substitution.
        pivot = Pivot(pivot_id=f"{match_id}:p{sub.minute}", match_id=match_id, minute=sub.minute, direction="away",
                      severity=2, status="confirmed", trigger_event_ids=[sub.event_id], chain_id="test")
        await adapters.matches.upsert_pivot(pivot)
        whatif = WhatIf(adapters, replays, OfflineModelClient(), runner=run_whatif, workers=0, runs_override=2)
        whatif.start()
        try:
            scenario = await whatif.submit(pivot.pivot_id, "cancel_substitution")
            while (scenario := whatif.get(scenario.scenario_id)).status not in ("completed", "failed"):
                await asyncio.sleep(0.05)
        finally:
            await whatif.stop()
        return pivot.pivot_id, scenario

    pivot_id, scenario = asyncio.run(first_run())
    assert scenario.status == "completed" and scenario.done == 4
    result = scenario.result
    assert result.executor == "local_pool" and result.narrative is not None
    assert result.baseline.home_win + result.baseline.draw + result.baseline.away_win == pytest.approx(1)

    async def after_restart():
        adapters, replays, match_id = await start()
        whatif = WhatIf(adapters, replays, OfflineModelClient(), runner=FakeRunner(), workers=0)
        assert whatif.get(scenario.scenario_id) is not None             # GET by id works after a restart
        traces = [t for t in await adapters.traces.list_traces(match_id) if t.input_ref == scenario.scenario_id]
        return whatif, traces

    whatif, traces = asyncio.run(after_restart())
    assert whatif.get(scenario.scenario_id).result == result
    assert [t.agent for t in traces] == ["executor", "comparator", "template"]
