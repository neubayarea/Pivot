import pytest


@pytest.fixture(autouse=True)
def _no_simulated_matches(monkeypatch, tmp_path):
    # The API builds PIVOT_SIM_MATCHES simulated matches at startup; tests that want them turn it back on.
    monkeypatch.setenv("PIVOT_SIM_MATCHES", "0")
    # Same for the recorded demo (eval/fixtures/demo-1021): tests that want it set PIVOT_DEMO_FIXTURE.
    monkeypatch.setenv("PIVOT_DEMO_FIXTURE", "0")
    # The AI's results go to PIVOT_DATA_DIR/results (Ax10): keep them out of the repo checkout.
    monkeypatch.setenv("PIVOT_DATA_DIR", str(tmp_path / "pivot-data"))
