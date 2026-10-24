from fastapi.testclient import TestClient

from pivot_api.app import app


def test_startup_builds_local_adapters(monkeypatch):
    monkeypatch.delenv("PIVOT_PROFILE", raising=False)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert app.state.adapters.profile == "local"
