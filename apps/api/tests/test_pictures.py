"""Shot map, heatmaps, pass network and average positions (Bx12). Points are in each team's
attacking view (CONV-002); the counts must be the events', and nothing may leave the pitch (CONV-001).
"""

import gzip
import json
import shutil
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from pivot_api import sims
from pivot_api.app import app
from pivot_core.domain import AveragePositionsReport, HeatmapReport, PassNetworkReport, ShotMap

DATA = json.loads(sims.FIXTURE.read_text(encoding="utf-8"))
MID = DATA["match"]["match_id"]
M = f"/api/matches/{MID}"
EVENTS = [e for e in DATA["events"] if e["period"] != 5]
KEEPERS = {p["player_id"] for t in ("home", "away") for p in DATA["match"][t]["squad"] if p["role"] == "GK"}
STARTERS = {t: [s["player_id"] for s in DATA["match"][t]["sheet"]["starters"]] for t in ("home", "away")}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PIVOT_DEMO_FIXTURE", str(sims.FIXTURE))
    monkeypatch.setenv("PIVOT_WHATIF_WARM", "0")
    monkeypatch.setenv("PIVOT_PREWARM_LANGS", "none")
    with TestClient(app) as c:
        yield c


def get(client, path, model, **params):
    r = client.get(M + path, params=params)
    assert r.status_code == 200, r.text
    return model.model_validate(r.json())


def inside(x, y):
    return 0 <= x <= 105 and 0 <= y <= 68


def test_conv_002_every_shot_is_there_and_attacks_x_105(client):
    shots = get(client, "/shots", ShotMap).shots
    assert [s.event_id for s in shots] == [e["event_id"] for e in EVENTS if e["type"] == "shot"]
    assert all(inside(s.x, s.y) and (s.end_x is None or inside(s.end_x, s.end_y)) for s in shots)
    goals = [s for s in shots if s.outcome == "goal"]
    assert goals and all(s.x > 80 for s in goals)          # both sides score at x = 105 in their own view
    for side in ("home", "away"):
        mine = [s.x for s in shots if s.team == side]
        assert sum(mine) / len(mine) > 75


def test_conv_002_up_to_and_period_cut_the_shots(client):
    early = get(client, "/shots", ShotMap, up_to=1500).shots
    assert early and all(s.t <= 1500 for s in early)
    second = get(client, "/shots", ShotMap, period=2)
    assert second.period == 2 and all(s.period == 2 for s in second.shots)
    assert len(second.shots) == sum(1 for e in EVENTS if e["type"] == "shot" and e["period"] == 2)


def test_conv_002_heatmaps_count_frames_and_keepers_stay_at_their_own_goal(client):
    h = get(client, "/heatmaps", HeatmapReport)
    assert h.source == "frames" and (h.cols, h.rows) == (21, 14)
    for grid in [*h.teams.values(), *h.players]:
        assert len(grid.cells) == h.cols * h.rows and max(grid.cells) == 1.0 and min(grid.cells) >= 0
    outfield = sum(p.samples for p in h.players if p.player_id not in KEEPERS)
    assert outfield == h.teams["home"].samples + h.teams["away"].samples     # team grids leave the keepers out
    raw = gzip.decompress(sims.FIXTURE.with_name("demo-1021.frames.json.gz").read_bytes())
    frames = [f for f in json.loads(raw) if f["period"] != 5]
    assert sum(p.samples for p in h.players) == sum(len(f["players"]) for f in frames)   # one per player per second
    for p in h.players:
        if p.player_id in KEEPERS:
            busiest = p.cells.index(1.0) % h.cols
            assert busiest <= 3, p.player_id                # the cell row by the own goal (x < 20 m)


def test_conv_002_pass_network_is_the_eleven_and_counts_completed_passes(client):
    net = get(client, "/pass-network", PassNetworkReport)
    pairs = Counter((e["player_id"], e["receiver_id"]) for e in EVENTS
                    if e["type"] == "pass" and e["outcome"] == "success" and e.get("receiver_id"))
    for side, team in net.teams.items():
        assert {n.player_id for n in team.nodes} == set(STARTERS[side])
        assert all(inside(n.x, n.y) for n in team.nodes)
        assert all(e.passes == pairs[e.from_id, e.to_id] and e.passes >= net.min_passes for e in team.edges)
        keeper = next(n for n in team.nodes if n.player_id in KEEPERS)
        assert keeper.x < 30 and keeper.x == min(n.x for n in team.nodes)
    fewer = get(client, "/pass-network", PassNetworkReport, min_passes=10)
    assert sum(len(t.edges) for t in fewer.teams.values()) < sum(len(t.edges) for t in net.teams.values())


def test_conv_002_average_positions_with_and_without_the_ball(client):
    pos = get(client, "/positions", AveragePositionsReport)
    played = {p for t in ("home", "away") for p in STARTERS[t]}
    assert played <= {p.player_id for p in pos.players}
    for p in pos.players:
        for pt in (p.in_possession, p.out_of_possession):
            assert pt is None or inside(pt.x, pt.y)
        if p.player_id in KEEPERS and p.in_possession:
            assert p.in_possession.x < 25
    for side in ("home", "away"):                           # a team stands higher with the ball than without
        mine = [p for p in pos.players if p.team == side and p.in_possession and p.out_of_possession]
        assert sum(p.in_possession.x for p in mine) > sum(p.out_of_possession.x for p in mine)


def test_without_frames_heatmaps_fall_back_to_events_and_positions_are_empty(tmp_path, monkeypatch):
    shutil.copy(sims.FIXTURE, tmp_path / "demo-1021.json")       # no frames file next to it
    monkeypatch.setenv("PIVOT_DEMO_FIXTURE", str(tmp_path / "demo-1021.json"))
    with TestClient(app) as c:
        h = get(c, "/heatmaps", HeatmapReport)
        pos = get(c, "/positions", AveragePositionsReport)
        net = get(c, "/pass-network", PassNetworkReport)
    assert h.source == "events" and h.teams["home"].samples > 0
    assert pos.players == []
    assert all(t.source == "events" and t.nodes for t in net.teams.values())


def test_unknown_match_and_bad_period_are_refused(client):
    for path in ("/shots", "/heatmaps", "/pass-network", "/positions"):
        assert client.get(f"/api/matches/nope{path}").status_code == 404
        assert client.get(M + path, params={"period": 5}).status_code == 422
