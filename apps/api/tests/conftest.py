import pytest


@pytest.fixture(autouse=True)
def _no_simulated_matches(monkeypatch):
    # The API builds PIVOT_SIM_MATCHES simulated matches at startup; tests that want them turn it back on.
    monkeypatch.setenv("PIVOT_SIM_MATCHES", "0")
