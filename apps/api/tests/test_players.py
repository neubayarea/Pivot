"""GET /api/matches/{id}/players/stats (Bx9): the focus-player card's numbers, no AI.

Test names carry the data definitions they check: RAT-001 (the player line and rating) and
MET-019 (distance, from the frames).
"""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from pivot_api import sims
from pivot_api.app import app
from pivot_core.analytics import StatCalculator, player_match_stats
from pivot_core.domain import Match, MatchEvent, Pivot, PlayerStatsReport, TrackingFrame

DATA = json.loads(sims.FIXTURE.read_text(encoding="utf-8"))
MID = DATA["match"]["match_id"]
URL = f"/api/matches/{MID}/players/stats"
STORED = {s["player_id"]: s for s in DATA["player_stats"]}
RED = next(e for e in DATA["events"] if e["type"] == "card" and e["foul"]["card"] in ("red", "second_yellow"))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PIVOT_DEMO_FIXTURE", str(sims.FIXTURE))
    monkeypatch.setenv("PIVOT_WHATIF_WARM", "0")
    monkeypatch.setenv("PIVOT_PREWARM_LANGS", "none")
    with TestClient(app) as c:
        # the worker is not running here, so put one pivot in by hand: the red card's minute
        minute = RED["t"] // 60
        pivot = Pivot(pivot_id=f"{MID}:p{minute}", match_id=MID, minute=minute, direction="home", severity=2,
                      status="pending", trigger_event_ids=[RED["event_id"]], chain_id="c-test")
        c.portal.call(app.state.adapters.matches.upsert_pivot, pivot)
        yield c


def report(client, **params) -> PlayerStatsReport:
    r = client.get(URL, params=params)
    assert r.status_code == 200, r.text
    return PlayerStatsReport.model_validate(r.json())


def test_rat_001_whole_match_serves_the_lines_saved_with_the_demo(client):
    rep = report(client)
    assert rep.source == "stored" and rep.match_id == MID
    served = {p.player_id: p.stats.model_dump(mode="json") for p in rep.players if p.stats}
    assert served == STORED
    squad = {p["player_id"] for t in ("home", "away") for p in DATA["match"][t]["squad"]}
    assert {p.player_id for p in rep.players} == squad          # unused substitutes are listed, with no stats


def test_rat_001_the_saved_lines_are_what_the_calculator_gives_at_full_time():
    # the "computed" path (any up_to before the whistle) uses the same code the demo file was made with
    frames = [TrackingFrame.model_validate(f) for f in sims.read_frames(sims.FIXTURE.with_name("demo-1021.frames.json.gz"))]
    calc = StatCalculator(Match.model_validate(DATA["match"]), [MatchEvent.model_validate(e) for e in DATA["events"]],
                          frames)
    assert {s.player_id: s.model_dump(mode="json") for s in player_match_stats(calc)} == STORED


def test_met_019_up_to_cuts_numbers_events_and_pivots_at_that_second(client):
    full, early = report(client), report(client, up_to=600)
    assert early.source == "computed" and early.up_to_t == 600
    by_id = {p.player_id: p for p in full.players}
    events = {e["event_id"]: e for e in DATA["events"]}
    for p in early.players:
        assert all(events[e]["t"] <= 600 for e in p.event_ids)
        assert not p.pivots                                       # the only pivot is later
        if p.stats:
            assert p.stats.up_to_t == 600 and p.stats.minutes_played <= 10
            assert p.stats.distance_km <= by_id[p.player_id].stats.distance_km
            assert p.stats.passes <= by_id[p.player_id].stats.passes


def test_rat_001_a_substitute_has_no_line_before_coming_on(client):
    sub = next(e for e in DATA["events"] if e["type"] == "substitution")
    on = sub["substitution"]["player_on_id"]
    before = report(client, up_to=sub["t"] - 60, player=on)
    after = report(client, player=on)
    assert [p.player_id for p in before.players] == [on] and before.players[0].stats is None
    assert after.players[0].stats is not None and sub["event_id"] in after.players[0].event_ids


def test_rat_001_the_sent_off_player_is_part_of_that_pivot(client):
    p = report(client, player=RED["player_id"]).players[0]
    link = next(x for x in p.pivots if x.minute == RED["t"] // 60)
    assert link.in_trigger and RED["event_id"] in link.event_ids
    assert p.stats.rating < 6.5                                   # RAT-001: a red card costs 1.5


def test_rat_001_a_simulated_match_serves_its_cached_lines(tmp_path, monkeypatch):
    monkeypatch.setenv("PIVOT_SIM_MATCHES", "1")
    monkeypatch.setenv("PIVOT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sims, "default_executor", lambda n: ThreadPoolExecutor(1))
    spec = sims.SPECS[0]
    with TestClient(app) as c:
        deadline = time.monotonic() + 180                         # until the background load has stored it
        while (s := c.get("/api/sims").json())["ready"] + s["failed"] < 1:
            assert time.monotonic() < deadline, s
            c.portal.call(asyncio.sleep, 0.05)
        url = f"/api/matches/{spec.match_id}/players/stats"
        whole, early = c.get(url).json(), c.get(url, params={"up_to": 1200}).json()
        data_path, _ = sims.paths(app.state.sims_dir, spec)
    cached = sims._read_json_gz(data_path)["player_stats"]
    assert whole["source"] == "stored"
    assert {p["player_id"]: p["stats"] for p in whole["players"] if p["stats"]} == {s["player_id"]: s for s in cached}
    assert early["source"] == "computed" and early["up_to_t"] == 1200


def test_unknown_player_or_match_is_refused(client):
    assert client.get(URL, params={"player": "x99"}).status_code == 422
    assert client.get("/api/matches/nope/players/stats").status_code == 404
    assert client.get(URL, params={"up_to": -5}).status_code == 422
