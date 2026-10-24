import pytest
from fastapi.testclient import TestClient

from pivot_api.app import app
from pivot_api.demo import DEMO_MATCH_ID

PIVOT_ID = f"{DEMO_MATCH_ID}:p61"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("PIVOT_PROFILE", raising=False)
    monkeypatch.delenv("PIVOT_DEMO", raising=False)
    with TestClient(app) as client:
        yield client


def test_list_matches_has_the_demo_match(client):
    response = client.get("/api/matches")
    assert response.status_code == 200
    assert [m["match_id"] for m in response.json()] == [DEMO_MATCH_ID]


def test_get_match_has_score_clock_status_and_lineups(client):
    match = client.get(f"/api/matches/{DEMO_MATCH_ID}").json()
    assert match["score"] == {"home": 1, "away": 2, "home_penalties": None, "away_penalties": None}
    assert (match["status"], match["clock"], match["period"]) == ("live", 75 * 60, 2)
    assert match["home"]["short_name"] == "HBC"
    assert len(match["away"]["sheet"]["starters"]) == 11


def test_unknown_match_is_404(client):
    assert client.get("/api/matches/nope").status_code == 404
    assert client.get("/api/matches/nope/timeline").status_code == 404
    assert client.get("/api/matches/nope/events").status_code == 404
    assert client.get("/api/matches/nope/pivots").status_code == 404


def test_timeline_is_one_metric_per_minute_in_order(client):
    timeline = client.get(f"/api/matches/{DEMO_MATCH_ID}/timeline").json()
    assert [m["minute"] for m in timeline] == list(range(75))
    assert all(-1 <= m["momentum"] <= 1 for m in timeline)
    assert timeline[30]["momentum"] > 0 > timeline[68]["momentum"]   # the swing after the 61' substitution


def test_events_since_returns_only_newer_events(client):
    events = client.get(f"/api/matches/{DEMO_MATCH_ID}/events").json()
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs) and seqs[0] == 0
    assert sum(e["shot_outcome"] == "goal" for e in events) == 3
    assert "clock_label" in events[0]                                  # computed fields are included
    later = client.get(f"/api/matches/{DEMO_MATCH_ID}/events", params={"since": seqs[-3]}).json()
    assert [e["seq"] for e in later] == seqs[-2:]


def test_pivots_list_and_detail(client):
    pivots = client.get(f"/api/matches/{DEMO_MATCH_ID}/pivots").json()
    assert [(p["minute"], p["status"]) for p in pivots] == [(61, "confirmed"), (71, "pending")]
    pivot = client.get(f"/api/pivots/{PIVOT_ID}").json()
    assert pivot["narrative"]["headline"]
    events = {e["event_id"] for e in client.get(f"/api/matches/{DEMO_MATCH_ID}/events").json()}
    assert set(pivot["trigger_event_ids"]) <= events                   # evidence points at real events


def test_unknown_pivot_is_404(client):
    assert client.get(f"/api/pivots/{DEMO_MATCH_ID}:p99").status_code == 404
    assert client.get("/api/pivots/garbage").status_code == 404


def test_negotiate_returns_the_local_websocket(client):
    assert client.post("/api/negotiate").json() == {"url": "ws://127.0.0.1:8000/api/ws"}
    url = client.post("/api/negotiate", params={"match_id": DEMO_MATCH_ID}).json()["url"]
    assert url == f"ws://127.0.0.1:8000/api/ws/matches/{DEMO_MATCH_ID}"


def test_cors_allows_the_vite_dev_server(client):
    response = client.get("/api/matches", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_openapi_lists_every_endpoint(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/api/matches", "/api/matches/{match_id}", "/api/matches/{match_id}/timeline",
            "/api/matches/{match_id}/events", "/api/matches/{match_id}/pivots", "/api/pivots/{pivot_id}",
            "/api/negotiate"} <= set(paths)


def test_demo_seed_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("PIVOT_DEMO", "0")
    with TestClient(app) as client:
        assert client.get("/api/matches").json() == []
