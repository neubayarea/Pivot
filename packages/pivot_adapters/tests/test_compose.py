import pytest

from pivot_adapters import build_adapters
from pivot_adapters.local import InMemoryWorkQueue


def test_local_is_default(monkeypatch):
    monkeypatch.delenv("PIVOT_PROFILE", raising=False)
    adapters = build_adapters()
    assert adapters.profile == "local"
    assert isinstance(adapters.queue, InMemoryWorkQueue)


def test_profile_from_env(monkeypatch):
    monkeypatch.setenv("PIVOT_PROFILE", "LOCAL")
    assert build_adapters().profile == "local"


def test_cloud_profiles_not_ready_and_unknown_rejected():
    with pytest.raises(NotImplementedError):
        build_adapters("c1")
    with pytest.raises(ValueError):
        build_adapters("prod")
