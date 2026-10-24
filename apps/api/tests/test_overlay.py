import json
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient

from pivot_api import overlay
from pivot_api.app import app
from pivot_api.demo import DEMO_MATCH_ID, demo_events, demo_match, demo_pivots

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "packages/contracts/schema/pivot.schema.json").read_text(encoding="utf-8"))
SUB_T = 61 * 60 + 5                           # the 61' substitution that triggers the demo pivot


def assert_schema(data, name):
    jsonschema.validate(data, {**SCHEMA, "$ref": f"#/$defs/{name}"})


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("PIVOT_PROFILE", raising=False)
    monkeypatch.delenv("PIVOT_DEMO", raising=False)
    with TestClient(app) as client:
        yield client


def overlay_at(client, clock=None):
    params = {} if clock is None else {"clock": clock}
    response = client.get(f"/api/matches/{DEMO_MATCH_ID}/overlay", params=params)
    assert response.status_code == 200, response.text
    assert_schema(response.json(), "OverlayFrame")
    return response.json()


def test_card_is_on_screen_for_twelve_seconds_from_its_trigger(client):
    frame = overlay_at(client, "61:10")
    card = frame["card"]
    assert (frame["clock"], card["show_at"], card["hide_at"]) == (3670, SUB_T, SUB_T + 12)
    assert card["minute_label"] == "62'" and card["direction_team"] == "Northgate Rovers"
    assert (card["severity"], card["status"]) == (2, "confirmed")
    assert card["headline"] and card["subline"]
    assert frame["scoreboard"] == {"home_short": "HBC", "away_short": "NGR", "period": 2, "clock_label": "62'",
                                   "score": {"home": 1, "away": 0, "home_penalties": None, "away_penalties": None}}


def test_no_card_outside_the_window(client):
    assert overlay_at(client, str(SUB_T - 1))["card"] is None
    assert overlay_at(client, str(SUB_T + 12))["card"] is None
    assert overlay_at(client, str(SUB_T))["card"] is not None      # seconds work as well as mm:ss


def test_default_clock_is_the_live_clock(client):
    frame = overlay_at(client)
    assert frame["clock"] == 75 * 60 and frame["card"] is None
    assert frame["scoreboard"]["score"]["away"] == 2 and frame["scoreboard"]["clock_label"] == "76'"


def test_timeline_has_only_checked_pivots(client):
    response = client.get(f"/api/matches/{DEMO_MATCH_ID}/overlay/timeline")
    assert_schema(response.json(), "OverlayTimeline")
    timeline = response.json()
    assert timeline["card_seconds"] == 12
    assert [c["pivot_id"] for c in timeline["cards"]] == [f"{DEMO_MATCH_ID}:p61"]   # the 71' one is pending


def test_bad_clock_and_unknown_match(client):
    assert client.get(f"/api/matches/{DEMO_MATCH_ID}/overlay", params={"clock": "1:2:3"}).status_code == 422
    assert client.get(f"/api/matches/{DEMO_MATCH_ID}/overlay", params={"clock": "999:00"}).status_code == 422
    assert client.get("/api/matches/nope/overlay").status_code == 404
    assert client.get("/api/matches/nope/overlay/timeline").status_code == 404


def test_overlapping_cards_give_way_to_the_latest():
    match, events = demo_match(), demo_events()
    p61, p71 = demo_pivots(events)
    earlier = p61.model_copy(update={"pivot_id": "x:p61b", "trigger_event_ids": []})   # shows at 61:00
    later = p71.model_copy(update={"status": "degraded", "narrative": p61.narrative})
    rejected = p61.model_copy(update={"pivot_id": "x:p70", "minute": 70, "status": "rejected"})
    timeline = overlay.build_timeline(match, [later, rejected, p61, earlier], events)

    assert [(c.pivot_id, c.show_at, c.hide_at) for c in timeline.cards] == [
        ("x:p61b", 3660, SUB_T), (p61.pivot_id, SUB_T, SUB_T + 12), (later.pivot_id, 71 * 60 + 50, 71 * 60 + 62)]
    assert overlay.frame_at(match, timeline, events, 3662).card.pivot_id == "x:p61b"
    assert overlay.frame_at(match, timeline, events, SUB_T + 1).card.pivot_id == p61.pivot_id
    assert overlay.frame_at(match, timeline, events, 71 * 60 + 55).card.status == "degraded"


def test_without_pivots_only_the_scoreboard():
    match, events = demo_match(), demo_events()
    timeline = overlay.build_timeline(match, [], events)
    frame = overlay.frame_at(match, timeline, events, 30 * 60)
    assert timeline.cards == [] and frame.card is None
    assert (frame.scoreboard.score.home, frame.scoreboard.score.away, frame.scoreboard.clock_label) == (1, 0, "31'")
    assert_schema(frame.model_dump(mode="json"), "OverlayFrame")


@pytest.mark.parametrize("value,t", [("63:20", 3800), ("0:00", 0), ("120:05", 7205), (" 3800 ", 3800)])
def test_parse_clock(value, t):
    assert overlay.parse_clock(value) == t
