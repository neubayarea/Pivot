"""The analyst's report (C19, #385): its shape, the deserved result, and parts that add up to the match."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from pivot_api import sims
from pivot_api.analysis import N_SIMS, PROFILE, MatchAnalysis, deserved, percentile
from pivot_api.app import app
from pivot_core.domain import MatchEvent

MATCH = json.loads(sims.FIXTURE.read_text(encoding="utf-8"))["match"]


@pytest.fixture(scope="module")
def client():
    mp = pytest.MonkeyPatch()
    mp.setenv("PIVOT_DEMO_FIXTURE", str(sims.FIXTURE))
    mp.setenv("PIVOT_SIM_MATCHES", "0")
    mp.setenv("PIVOT_WHATIF_WARM", "0")
    mp.setenv("PIVOT_PREWARM_LANGS", "none")
    with TestClient(app) as c:
        yield c
    mp.undo()


@pytest.fixture(scope="module")
def report(client) -> dict:
    r = client.get(f"/api/matches/{MATCH['match_id']}/analysis")
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def stats(client) -> dict:
    return client.get(f"/api/matches/{MATCH['match_id']}/stats", params={"scope": "match"}).json()["scopes"][0]


def test_the_report_has_every_part_in_the_contract_shape(report):
    MatchAnalysis.model_validate(report)
    assert set(report) >= {"deserved", "phases", "game_state", "shot_quality", "lanes", "profile"}
    assert [(p["from"], p["to"]) for p in report["phases"]] == [(0, 15), (15, 30), (30, 45), (45, 60), (60, 75), (75, 90)]
    assert set(report["phases"][0]["home"]) == {"xg", "field_tilt_pct", "possession_pct", "ppda", "shots"}
    assert set(report["shot_quality"]["away"]["by_source"]) == {"open_play", "set_piece", "penalty", "counter"}
    assert set(report["lanes"]["home"]) == {"left", "centre", "right"}
    assert report["profile"]["metrics"] == list(PROFILE) and len(report["profile"]["home"]) == len(PROFILE)
    assert report["profile"]["baseline_matches"] >= 1


def test_the_deserved_result_is_a_probability_and_comes_out_the_same_every_time(report):
    d = report["deserved"]
    assert d["n_sims"] == N_SIMS
    assert d["home_win"] + d["draw"] + d["away_win"] == pytest.approx(1.0, abs=1e-3)
    assert d["xpts"]["home"] == pytest.approx(3 * d["home_win"] + d["draw"], abs=0.01)
    assert 0 <= d["xpts"]["away"] <= 3


def test_deserved_follows_the_chances():
    shot = lambda team, xg, i: MatchEvent.model_validate({   # noqa: E731
        "event_id": f"s{i}", "match_id": "m", "seq": i, "t": 60 * i, "period": 1, "period_t": 60 * i, "type": "shot",
        "team": team,
        "player_id": "p", "xg": xg, "shot_outcome": "saved"})
    sure = deserved([shot("home", 0.99, i) for i in range(3)] + [shot("away", 0.01, 9)], seed=1)
    assert sure.home_win > 0.95 and sure.home_win + sure.draw + sure.away_win == pytest.approx(1.0, abs=1e-3)
    none = deserved([], seed=1)
    assert (none.home_win, none.draw, none.away_win) == (0.0, 1.0, 0.0)
    assert deserved([shot("home", 0.4, 1)], seed=7) == deserved([shot("home", 0.4, 1)], seed=7)


def test_the_phases_add_up_to_the_match(report, stats):
    for side in ("home", "away"):
        assert sum(p[side]["xg"] or 0 for p in report["phases"]) == pytest.approx(stats[side]["xg"], abs=0.02)
        assert sum(p[side]["shots"] or 0 for p in report["phases"]) == stats[side]["shots"]
    windows = [p["window"] for p in report["phases"]]
    assert all(a[1] == b[0] for a, b in zip(windows, windows[1:]))      # contiguous, so nothing is counted twice


def test_the_game_states_cover_the_match_and_its_xg(report, stats):
    states = report["game_state"]
    assert {s["state"] for s in states} <= {"level", "home_leading", "away_leading"}
    played = sum(min(p["end_t"], 10**9) - p["start_t"] for p in MATCH["periods"] if p["period"] != 5) / 60
    assert sum(s["minutes"] for s in states) == pytest.approx(played, abs=1.5)
    for side in ("home", "away"):
        xg = sum(s[side]["xg_per90"] * s["minutes"] / 90 for s in states)
        assert xg == pytest.approx(stats[side]["xg"], abs=0.05)


def test_shot_quality_and_lanes_add_up(report, stats):
    for side in ("home", "away"):
        q = report["shot_quality"][side]
        assert q["shots"] == stats[side]["shots"]
        assert sum(q["by_source"].values()) == pytest.approx(stats[side]["xg"], abs=0.02)
        assert q["xg_per_shot"] == pytest.approx(stats[side]["xg"] / stats[side]["shots"], abs=0.005)
        lanes = report["lanes"][side]
        assert sum(v["xg"] for v in lanes.values()) == pytest.approx(stats[side]["xg"], abs=0.03)
        assert sum(v["entries"] for v in lanes.values()) == stats[side]["box_entries"]


def test_percentiles_and_the_inverted_press():
    assert percentile(5.0, [1.0, 5.0, 9.0, 10.0], inverted=False) == 50.0
    assert percentile(5.0, [1.0, 5.0, 9.0, 10.0], inverted=True) == 75.0       # a low PPDA is a hard press
    assert percentile(None, [1.0], inverted=False) is None and percentile(1.0, [], inverted=False) is None


def test_up_to_counts_only_what_happened_by_then(client, report):
    early = client.get(f"/api/matches/{MATCH['match_id']}/analysis", params={"up_to": 20 * 60}).json()
    assert early["up_to_t"] == 1200 and len(early["phases"]) == 3
    total = lambda r: sum(q["shots"] for q in r["shot_quality"].values())   # noqa: E731
    assert total(early) <= total(report)
    assert client.get("/api/matches/no-such-match/analysis").status_code == 404
