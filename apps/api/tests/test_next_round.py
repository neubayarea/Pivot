"""The next round (C14, #354): matchday 31's fixtures, before kick-off, with predictions read from a file."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from pivot_api import nextround, sims
from pivot_api.app import app
from pivot_api.prematch import matchday_of, prematch
from pivot_api.whatif import portable_sim_version
from pivot_core.sim.world import HBC, ROV

SEASON = sims._season()


@pytest.fixture(scope="module")
def matches():
    return [nextround.next_match(fx, SEASON) for fx in nextround.fixtures()]


def test_the_round_is_matchday_31_with_the_site_s_two_clubs_first(matches):
    assert len(matches) == nextround.SHOWN
    assert all(m.status == "scheduled" and m.match_id.startswith("S2026-31-") for m in matches)
    ours = {HBC.club_id, ROV.club_id}
    assert all({m.home.club_id, m.away.club_id} & ours for m in matches[:2])
    assert len({c for m in matches for c in (m.home.club_id, m.away.club_id)}) == 2 * len(matches)   # no club twice


def test_each_fixture_has_its_pre_match_report(matches):
    for m in matches:
        assert matchday_of(m) == 31
        report = prematch(m, SEASON)
        assert report is not None and report.matchday == 31
        assert report.teams["home"].club_id == m.home.club_id
        assert m.context.form and m.context.head_to_head is not None


def test_a_prediction_file_from_another_simulator_is_not_used(tmp_path):
    path = tmp_path / "matchday-31.json"
    fixture = {"match_id": "S2026-31-LUN-HBC", "prediction": {"home_win": 0.2}}
    path.write_text(json.dumps({"sim_version": "old", "fixtures": [fixture]}), encoding="utf-8")
    assert nextround.read(path, portable_sim_version()) == {}
    path.write_text(json.dumps({"sim_version": portable_sim_version(), "fixtures": [fixture]}), encoding="utf-8")
    assert nextround.read(path, portable_sim_version()) == {"S2026-31-LUN-HBC": {"home_win": 0.2}}
    assert nextround.read(tmp_path / "missing.json", "x") == {}


def test_the_committed_predictions_are_for_this_simulator_and_add_up():
    data = json.loads(nextround.PATH.read_text(encoding="utf-8"))
    assert data["sim_version"] == portable_sim_version()
    assert [f["match_id"] for f in data["fixtures"]] == [nextround.next_match(fx, None).match_id
                                                         for fx in nextround.fixtures()]
    for f in data["fixtures"]:
        p = f["prediction"]
        assert p["n_runs"] == nextround.N_RUNS
        assert p["home_win"] + p["draw"] + p["away_win"] == pytest.approx(1)
        assert all(lo <= p[k] <= hi for k, (lo, hi) in p["ci95"].items())
        assert 1 <= len(p["scorelines"]) <= nextround.TOP_SCORELINES


def test_the_hub_lists_the_round_and_the_fixtures_open_before_kick_off(monkeypatch):
    for name in ("PIVOT_PROFILE", "PIVOT_DEMO", "PIVOT_FOUNDRY_ENDPOINT", "PIVOT_NEXT_ROUND"):
        monkeypatch.delenv(name, raising=False)
    with TestClient(app) as client:
        nxt = client.get("/api/hub").json()["next"]
        assert nxt["matchday"] == 31
        ids = [f["match_id"] for f in nxt["fixtures"]]
        assert len(ids) == nextround.SHOWN
        assert all(f["prediction"] is not None for f in nxt["fixtures"])
        match = client.get(f"/api/matches/{ids[0]}").json()
        assert match["status"] == "scheduled"
        assert client.get(f"/api/matches/{ids[0]}/prematch").json()["matchday"] == 31


def test_the_schedule_is_every_round_still_to_come_a_week_apart(monkeypatch):
    """C15: matchdays 31-38, ten fixtures each, every club once a round, and odds only where worked out."""
    for name in ("PIVOT_PROFILE", "PIVOT_DEMO", "PIVOT_FOUNDRY_ENDPOINT", "PIVOT_NEXT_ROUND"):
        monkeypatch.delenv(name, raising=False)
    with TestClient(app) as client:
        body = client.get("/api/hub").json()
        rounds = body["schedule"]
        assert [r["matchday"] for r in rounds] == list(range(31, nextround.LAST_MATCHDAY + 1))
        assert body["next"]["matchday"] == 31 and body["next"]["fixtures"] == rounds[0]["fixtures"]
        assert [r["date"] for r in rounds[:2]] == ["2026-10-28", "2026-11-04"]
        for r in rounds:
            clubs = [f[s]["short_name"] for f in r["fixtures"] for s in ("home", "away")]
            assert len(r["fixtures"]) == 10 and len(set(clubs)) == 20
            worked_out = nextround.path_for(r["matchday"]).is_file()
            assert all((f["prediction"] is not None) == worked_out for f in r["fixtures"])
        later = rounds[-1]["fixtures"][0]["match_id"]
        assert client.get(f"/api/matches/{later}").json()["status"] == "scheduled"
        assert client.get(f"/api/matches/{later}/prematch").json()["matchday"] == nextround.LAST_MATCHDAY
        assert later not in [m["match_id"] for m in client.get("/api/matches").json()]
