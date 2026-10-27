"""Bx18: a chip whose replays fail is not run again, so a viewer is told at once instead of waiting minutes."""

import time
from concurrent.futures.process import BrokenProcessPool

import pytest
from fastapi.testclient import TestClient

from pivot_api.app import app
from pivot_api.demo import DEMO_MATCH_ID, demo_match
from pivot_api.sims import Replay
from pivot_api.whatif import REPLAY_FAILS, WhatIf
from pivot_core.domain import OutcomeDist, SimResult

PIVOT_ID = f"{DEMO_MATCH_ID}:p61"


def dist(home: float, draw: float) -> OutcomeDist:
    away = round(1 - home - draw, 6)
    return OutcomeDist(home_win=home, draw=draw, away_win=away,
                       ci95={"home_win": (home - .05, home + .05), "draw": (draw - .05, draw + .05),
                             "away_win": (max(0, away - .05), away + .05)})


class FakeRunner:
    """Stands in for run_whatif, as in test_whatif.py: a fixed result."""

    def __init__(self) -> None:
        self.calls = []

    def __call__(self, match, spec, *, seed, plants, progress, pool, workers, scenario_id, n_runs):
        self.calls.append(spec)
        progress(2 * n_runs, 2 * n_runs)
        return SimResult(scenario_id=scenario_id, baseline=dist(.2, .3), counterfactual=dist(.6, .2),
                         significant={"home_win": True, "draw": False, "away_win": True}, runtime_ms=5,
                         executor="local_pool")


def wait_done(client, scenario_id, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        scenario = client.get(f"/api/scenarios/{scenario_id}").json()
        if scenario["status"] in ("completed", "failed"):
            return scenario
        time.sleep(0.05)
    raise AssertionError(f"{scenario_id} still {scenario['status']}")


class FailingRunner(FakeRunner):
    """Fails one chip the way the simulator's KeyError(None) does (#345), from `fail_at` runs per arm up;
    `error` lets a test fail it with something that says nothing about the chip."""

    def __init__(self, type_: str, fail_at: int = 200, error: Exception | None = None) -> None:
        super().__init__()
        self.type, self.fail_at, self.error = type_, fail_at, error

    def __call__(self, match, spec, **kw):
        if spec.type == self.type and kw["n_runs"] >= self.fail_at:
            self.calls.append(spec)
            raise self.error or KeyError(None)
        return super().__call__(match, spec, **kw)


def client_with(monkeypatch, runner):
    monkeypatch.delenv("PIVOT_PROFILE", raising=False)
    monkeypatch.delenv("PIVOT_DEMO", raising=False)
    monkeypatch.delenv("PIVOT_FOUNDRY_ENDPOINT", raising=False)
    client = TestClient(app)
    client.__enter__()
    whatif: WhatIf = app.state.whatif
    whatif.runner, whatif.workers = runner, 0
    whatif.replays[DEMO_MATCH_ID] = Replay("v1", demo_match)
    return client


@pytest.fixture
def make_client(monkeypatch):
    clients = []

    def make(runner):
        clients.append(client_with(monkeypatch, runner))
        return clients[-1]

    yield make
    for c in clients:
        c.__exit__(None, None, None)


def post(client, type_, **body):
    return client.post("/api/scenarios", json={"pivot_id": PIVOT_ID, "type": type_, **body})


def chips(client) -> dict[str, dict]:
    return {c["type"]: c for c in client.get(f"/api/pivots/{PIVOT_ID}/scenarios").json()}


def test_a_chip_whose_replays_fail_is_greyed_out_and_refused_without_running_again(make_client):
    runner = FailingRunner("cancel_substitution")
    client = make_client(runner)
    assert chips(client)["cancel_substitution"]["enabled"]
    first = post(client, "cancel_substitution")
    assert first.status_code == 202
    assert wait_done(client, first.json()["scenario_id"])["status"] == "failed"

    chip = chips(client)["cancel_substitution"]
    assert (chip["enabled"], chip["disabled_reason"]) == (False, REPLAY_FAILS)
    for n_runs in (200, 500, 1000):                    # more runs replay the same seeds and more
        again = post(client, "cancel_substitution", n_runs=n_runs)
        assert again.status_code == 422 and REPLAY_FAILS in again.json()["detail"]
    assert len(runner.calls) == 1                      # never run again

    other = post(client, "remove_goal")                # the other chips are untouched
    assert wait_done(client, other.json()["scenario_id"])["status"] == "completed"
    assert chips(client)["remove_goal"]["enabled"]


def test_a_failure_at_500_runs_leaves_200_runs_on_offer(make_client):
    runner = FailingRunner("remove_goal", fail_at=500)
    client = make_client(runner)
    failed = post(client, "remove_goal", n_runs=500)
    assert wait_done(client, failed.json()["scenario_id"])["status"] == "failed"
    assert chips(client)["remove_goal"]["enabled"]
    assert post(client, "remove_goal", n_runs=1000).status_code == 422
    ok = post(client, "remove_goal", n_runs=200)
    assert ok.status_code == 202 and wait_done(client, ok.json()["scenario_id"])["status"] == "completed"


def test_another_minute_for_a_moved_substitution_is_another_chip(make_client):
    runner = FailingRunner("move_substitution")
    client = make_client(runner)
    failed = post(client, "move_substitution", params={"new_minute": 80})
    assert wait_done(client, failed.json()["scenario_id"])["status"] == "failed"
    assert post(client, "move_substitution", params={"new_minute": 80}).status_code == 422
    assert chips(client)["move_substitution"]["enabled"]            # offered with its default minute, 74
    again = post(client, "move_substitution")                       # 74: never tried, so it runs
    assert again.status_code == 202
    wait_done(client, again.json()["scenario_id"])                  # the runner is called in the background
    assert len(runner.calls) == 2


@pytest.mark.parametrize("error", [BrokenProcessPool("a worker died"), MemoryError(), OSError("disk full")])
def test_a_failure_that_says_nothing_about_the_chip_can_be_run_again(make_client, error):
    runner = FailingRunner("cancel_substitution", error=error)
    client = make_client(runner)
    first = post(client, "cancel_substitution")
    assert wait_done(client, first.json()["scenario_id"])["status"] == "failed"
    assert chips(client)["cancel_substitution"]["enabled"]
    again = post(client, "cancel_substitution")
    assert again.status_code == 202 and again.json()["scenario_id"] != first.json()["scenario_id"]
    assert wait_done(client, again.json()["scenario_id"])["status"] == "failed"
    assert len(runner.calls) == 2
