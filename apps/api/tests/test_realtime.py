import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pivot_api.app import app
from pivot_api.demo import DEMO_MATCH_ID

WS = f"/api/ws/matches/{DEMO_MATCH_ID}"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("PIVOT_PROFILE", raising=False)
    monkeypatch.delenv("PIVOT_DEMO", raising=False)
    with TestClient(app) as client:
        yield client


def publish(client, type_="metric.updated", **payload):
    response = client.post(f"/api/dev/matches/{DEMO_MATCH_ID}/publish", json={"type": type_, "payload": payload})
    assert response.status_code == 202
    return response.json()["seq"]


def test_subscriber_receives_broadcasts_in_seq_order(client):
    with client.websocket_connect(WS) as ws:
        first = publish(client, minute=76, momentum=-0.4)
        publish(client, "pivot.rejected", pivotId=f"{DEMO_MATCH_ID}:p71")
        a, b = ws.receive_json(), ws.receive_json()
    assert (a["type"], a["match_id"], a["seq"], a["payload"]["minute"]) == ("metric.updated", DEMO_MATCH_ID, first, 76)
    assert (b["type"], b["seq"]) == ("pivot.rejected", first + 1)
    assert set(a) == {"type", "match_id", "seq", "ts", "payload"}


def test_every_client_receives_each_broadcast(client):
    with client.websocket_connect(WS) as one, client.websocket_connect(WS) as two:
        seq = publish(client, minute=77)
        assert one.receive_json()["seq"] == two.receive_json()["seq"] == seq


def test_reconnect_with_since_resends_the_missed_envelopes_then_goes_live(client):
    with client.websocket_connect(WS) as ws:
        publish(client, minute=78)
        last = ws.receive_json()["seq"]
    missed = [publish(client, minute=m) for m in (79, 80, 81)]      # sent while disconnected
    with client.websocket_connect(f"{WS}?since={last}") as ws:
        assert [ws.receive_json()["seq"] for _ in missed] == missed
        live = publish(client, minute=82)
        assert ws.receive_json()["seq"] == live                     # nothing resent twice


def test_since_from_before_a_server_restart_resends_everything(client):
    seq = publish(client, minute=83)
    with client.websocket_connect(f"{WS}?since=9999") as ws:
        assert ws.receive_json()["seq"] == seq


def test_unknown_match_is_closed(client):
    with client.websocket_connect("/api/ws/matches/nope") as ws, pytest.raises(WebSocketDisconnect) as closed:
        ws.receive_json()
    assert closed.value.code == 4404


def test_negotiate_points_at_the_match_websocket(client):
    url = client.post("/api/negotiate", params={"match_id": DEMO_MATCH_ID}).json()["url"]
    assert url.endswith(WS)
