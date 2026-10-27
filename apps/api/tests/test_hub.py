"""The match centre's list (C14, #354): every stored match, and the one played as live on the wall clock."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pivot_api import hub
from pivot_api.app import app
from pivot_api.demo import DEMO_MATCH_ID


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("PIVOT_PROFILE", raising=False)
    monkeypatch.delenv("PIVOT_DEMO", raising=False)
    monkeypatch.delenv("PIVOT_FOUNDRY_ENDPOINT", raising=False)
    monkeypatch.delenv("PIVOT_LIVE_MATCH", raising=False)
    with TestClient(app) as c:
        yield c


def test_every_listed_match_has_a_line_in_the_same_order(client):
    listed = [m["match_id"] for m in client.get("/api/matches").json()]
    body = client.get("/api/hub").json()
    assert [m["match_id"] for m in body["matches"]] == listed
    demo = next(m for m in body["matches"] if m["match_id"] == DEMO_MATCH_ID)
    assert set(demo) >= {"matchday", "status", "home", "away", "score", "pivots", "best", "live", "length_s"}
    assert demo["home"]["short_name"] and demo["home"]["color"].startswith("#")
    assert isinstance(demo["pivots"], int)
    assert sum(m["live"] for m in body["matches"]) == (body["live"] is not None)


def test_the_live_clock_wraps_round_after_the_final_whistle_and_a_break():
    length = 96 * 60
    cycle = length + hub.LIVE_BREAK_S
    assert hub.live_clock(length, hub.LIVE_ANCHOR) == 0
    assert hub.live_clock(length, hub.LIVE_ANCHOR + 600) == 600
    assert hub.live_clock(length, hub.LIVE_ANCHOR + cycle + 61) == 61
    assert all(0 <= hub.live_clock(length, hub.LIVE_ANCHOR + s * 997) < cycle for s in range(50))


class M:
    def __init__(self, match_id, status="finished", preset=None):
        self.match_id, self.status, self.preset = match_id, status, preset


def test_the_live_match_is_the_second_finished_simulated_one_unless_asked(monkeypatch):
    matches = [M("M-seed-101"), M("M-seed-212"), M("M-seed-303"), M("demo", preset="demo-1021")]
    assert hub.live_id(matches) == "M-seed-212"
    monkeypatch.setenv("PIVOT_LIVE_MATCH", "M-seed-303")
    assert hub.live_id(matches) == "M-seed-303"
    monkeypatch.setenv("PIVOT_LIVE_MATCH", "M-seed-999")              # not stored: the default again
    assert hub.live_id(matches) == "M-seed-212"
    assert hub.live_id([M("M-seed-101")]) == "M-seed-101"
    assert hub.live_id([M("M-seed-101", status="live")]) is None


def test_the_league_history_lists_every_played_round_with_scores(client):
    history = client.get("/api/hub").json()["history"]
    assert [r["matchday"] for r in history] == list(range(29, 0, -1))
    assert sum(len(r["results"]) for r in history) == 290
    game = history[-1]["results"][0]
    assert set(game) == {"home", "away", "score", "reds", "match_id"}
    assert game["home"]["short_name"] and game["home"]["color"].startswith("#")
    assert history[0]["date"] < "2026-10-21"
    assert all(g["match_id"] is None for r in history for g in r["results"])   # no fixture replays stored yet
    assert sum(g["reds"]["home"] + g["reds"]["away"] for r in history for g in r["results"]) > 0


def test_a_season_fixture_spec_builds_the_match_the_season_file_was_played_from(monkeypatch):
    from pivot_api import sims
    from pivot_core.sim.world import fixture_match, schedule

    spec = sims.FixtureSpec.from_id("S2026-14-ELM-SAL")
    fx = next(f for f in schedule() if f.matchday == 14 and f.home == "club-elm")
    assert (spec.seed, spec.match_id) == (fx.seed, fixture_match(fx).match_id)
    assert spec.build() == fixture_match(fx) == spec.replay().build()
    monkeypatch.setenv("PIVOT_SIM_FIXTURES", "S2026-14-ELM-SAL, S2099-01-AAA-BBB")
    assert [s.match_id for s in sims.fixture_specs_from_env()] == ["S2026-14-ELM-SAL"]
    monkeypatch.delenv("PIVOT_SIM_FIXTURES")
    assert sims.fixture_specs_from_env() == []
