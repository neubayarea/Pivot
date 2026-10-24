import asyncio
import json

from fastapi.testclient import TestClient

from pivot_api.single import build_app
from pivot_core.domain import PivotCandidate
from pivot_core.ports import PIVOT_CANDIDATES


def _dist(tmp_path):
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    return tmp_path


def test_serves_web_build_with_spa_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("PIVOT_WORKER", "0")
    with TestClient(build_app(_dist(tmp_path))) as client:
        assert client.get("/").text == "<div id=root></div>"
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert client.get("/pivots/M-1:p61").text == "<div id=root></div>"   # client-side route
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/api/matches").status_code == 200
        assert client.get("/api/nope").status_code == 404                     # not the SPA


def test_api_only_without_web_build(tmp_path, monkeypatch):
    monkeypatch.setenv("PIVOT_WORKER", "0")
    with TestClient(build_app(tmp_path)) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/").status_code == 404


def test_embedded_worker_shares_the_api_adapters(tmp_path, monkeypatch):
    monkeypatch.delenv("PIVOT_WORKER", raising=False)
    app = build_app(tmp_path)
    candidate = PivotCandidate(match_id="M-api-demo", minute=50, direction="home", cusum_stat=4.0, swing=0.3,
                               key_event_ids=[], window=(45, 55))
    with TestClient(app) as client:
        adapters = app.state.adapters

        async def send_and_wait():
            await adapters.queue.send(PIVOT_CANDIDATES, "M-api-demo:50", candidate.model_dump(mode="json"))
            for _ in range(200):
                if await adapters.matches.get_pivot("M-api-demo", "M-api-demo:p50"):
                    return
                await asyncio.sleep(0.01)

        client.portal.call(send_and_wait)
        assert client.get("/api/pivots/M-api-demo:p50").json()["status"] == "confirmed"



def test_embedded_worker_pushes_to_the_websocket(tmp_path, monkeypatch):
    monkeypatch.delenv("PIVOT_WORKER", raising=False)
    app = build_app(tmp_path)
    candidate = PivotCandidate(match_id="M-api-demo", minute=52, direction="home", cusum_stat=4.0, swing=0.3,
                               key_event_ids=[], window=(47, 57))
    with TestClient(app) as client, client.websocket_connect("/api/ws/matches/M-api-demo") as ws:
        client.portal.call(app.state.adapters.queue.send, PIVOT_CANDIDATES, "M-api-demo:52",
                           candidate.model_dump(mode="json"))
        types = []
        while not types or not types[-1].startswith("pivot."):
            types.append(json.loads(ws.receive_text())["type"])
        assert types[-1] == "pivot.confirmed"
        assert "trace.appended" in types
