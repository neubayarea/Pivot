"""GET /api/matches/{id}/stats (Bx11): the 23 team stats of docs/data-definitions.md §4 (MET-001 to
MET-023) per part of the match, with their labels. Test names carry the definitions they check.
"""

import asyncio
import json
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pivot_api import sims
from pivot_api.app import app
from pivot_api.team_stats import GROUPS
from pivot_core.analytics import StatCalculator, team_stats
from pivot_core.domain import STAT_UNITS, Match, MatchEvent, TeamStatsReport, TrackingFrame

DATA = json.loads(sims.FIXTURE.read_text(encoding="utf-8"))
MID = DATA["match"]["match_id"]
URL = f"/api/matches/{MID}/stats"
FRAME_METRICS = {"possession_pct", "line_height_m", "team_width_m", "press_distance_m", "distance_covered_km"}
DOCS = Path(__file__).resolve().parents[3] / "docs" / "data-definitions.md"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PIVOT_DEMO_FIXTURE", str(sims.FIXTURE))
    monkeypatch.setenv("PIVOT_WHATIF_WARM", "0")
    monkeypatch.setenv("PIVOT_PREWARM_LANGS", "none")
    with TestClient(app) as c:
        yield c


def report(client, url=URL, **params) -> TeamStatsReport:
    r = client.get(url, params=params)
    assert r.status_code == 200, r.text
    return TeamStatsReport.model_validate(r.json())


def as_rows(rep: TeamStatsReport) -> list[dict]:
    return [{"scope": s.scope, "period": s.period, "window": list(s.window), "home": s.home, "away": s.away}
            for s in rep.scopes]


def test_met_001_to_023_whole_match_equals_the_table_kept_with_the_demo(client):
    # the same table make_demo.py wrote, so moving team_stats() into pivot_core changed nothing
    assert as_rows(report(client)) == DATA["team_stats"]


def test_met_001_to_023_a_simulated_match_equals_the_stat_calculator(tmp_path, monkeypatch):
    monkeypatch.setenv("PIVOT_SIM_MATCHES", "1")
    monkeypatch.setenv("PIVOT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sims, "default_executor", lambda n: ThreadPoolExecutor(1))
    spec = sims.SPECS[0]
    with TestClient(app) as c:
        deadline = time.monotonic() + 180                     # until the background load has stored it
        while (s := c.get("/api/sims").json())["ready"] + s["failed"] < 1:
            assert time.monotonic() < deadline, s
            c.portal.call(asyncio.sleep, 0.05)
        rep = report(c, f"/api/matches/{spec.match_id}/stats")
        data_path, frames_path = sims.paths(app.state.sims_dir, spec)
    data = sims._read_json_gz(data_path)
    calc = StatCalculator(Match.model_validate(data["match"]), [MatchEvent.model_validate(e) for e in data["events"]],
                          [TrackingFrame.model_validate(f) for f in sims.read_frames(frames_path)])
    assert as_rows(rep) == team_stats(calc)
    assert [s.scope for s in rep.scopes][:3] == ["match", "first_half", "second_half"]


def test_met_006_halves_are_cut_at_the_whistle_and_add_up(client):
    rep = report(client)
    by = {s.scope: s for s in rep.scopes}
    first, second = by["first_half"], by["second_half"]
    assert (first.period, second.period) == (1, 2)
    shots = {p: sum(1 for e in DATA["events"] if e["type"] == "shot" and e["team"] == "home" and e["period"] == p)
             for p in (1, 2)}
    assert (first.home["shots"], second.home["shots"]) == (shots[1], shots[2])
    for metric in ("shots", "passes", "pressures", "tackles_won", "turnovers"):
        for side in ("home", "away"):
            assert getattr(first, side)[metric] + getattr(second, side)[metric] == getattr(by["match"], side)[metric]
    assert [s.scope for s in report(client, scope="second_half").scopes] == ["second_half"]


def test_met_019_no_frames_means_null_not_zero(client, tmp_path, monkeypatch):
    # the same match without its frames file next to it: the stats that need frames have no answer
    shutil.copy(sims.FIXTURE, tmp_path / "demo-1021.json")
    monkeypatch.setenv("PIVOT_DEMO_FIXTURE", str(tmp_path / "demo-1021.json"))
    with TestClient(app) as c:
        rep = report(c)
    for s in rep.scopes:
        for side in (s.home, s.away):
            assert all(side[m] is None for m in FRAME_METRICS)
            assert side["shots"] is not None and side["passes"] > 0


def test_met_021_a_window_with_nothing_to_divide_by_is_null(client):
    rep = report(client, **{"from": 0, "to": 1})                 # the first minute only
    s = rep.scopes[0]
    assert s.scope == "window" and list(s.window) == [0, 1]
    nulls = [m for side in (s.home, s.away) for m, v in side.items() if v is None]
    assert nulls and all(v is None or isinstance(v, float) for side in (s.home, s.away) for v in side.values())


def test_met_006_up_to_counts_only_what_happened_by_then(client):
    rep = report(client, up_to=1200)
    assert rep.up_to_t == 1200
    assert [(s.scope, list(s.window)) for s in rep.scopes] == [("match", [0, 21]), ("first_half", [0, 21])]
    by = {s.scope: s for s in rep.scopes}
    for side in ("home", "away"):
        shots = sum(1 for e in DATA["events"] if e["type"] == "shot" and e["team"] == side and e["t"] <= 1200)
        assert getattr(by["match"], side)["shots"] == shots
    full = {s.scope: s for s in report(client).scopes}
    assert by["match"].home["distance_covered_km"] < full["match"].home["distance_covered_km"]


def test_met_ids_units_and_groups_match_the_data_definitions(client):
    rep = report(client)
    documented = dict(re.findall(r"^\| (MET-0\d\d) \| `(\w+)` \|", DOCS.read_text(encoding="utf-8"), re.M))
    assert {m.definition_id: m.metric for m in rep.metrics} == documented
    assert {m.metric: m.unit for m in rep.metrics} == STAT_UNITS
    assert [m.metric for m in rep.metrics] == [m for metrics in GROUPS.values() for m in metrics]
    assert all(m.label and m.fan_label and m.description for m in rep.metrics)


def test_unknown_match_and_bad_window_are_refused(client):
    assert client.get("/api/matches/nope/stats").status_code == 404
    assert client.get(URL, params={"from": 30, "to": 20}).status_code == 422
    assert client.get(URL, params={"scope": "window"}).status_code == 422
    assert client.get(URL, params={"up_to": -1}).status_code == 422
