"""Bx14: the site's simulated matches have What-ifs run ahead of time too, one file per match in
eval/fixtures/whatif/, made by `scripts/make_whatif_fixture.py --match ...` and read at startup."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import pivot_api.app as app_module
import pivot_core.analytics as analytics_pkg
import pivot_core.sim as sim_pkg
from pivot_api import sims
from pivot_api.app import app
from pivot_api.sims import SIM_VERSION
from pivot_api.whatif import (
    SEED_PRECOMPUTED_DIR, cache_key, load_precomputed, portable_sim_version, precomputed_path, write_precomputed,
)

SITE = {s.match_id for s in sims.specs_first(40)}


def _crlf_checkout() -> bool:
    return any(b"\r\n" in p.read_bytes() for pkg in (sim_pkg, analytics_pkg)
               for p in Path(pkg.__file__).parent.glob("*.py"))


def test_the_portable_version_is_the_servers_version():
    if _crlf_checkout():
        pytest.skip("CRLF checkout (Windows): SIM_VERSION here hashes other bytes; CI checks this on LF")
    assert portable_sim_version() == SIM_VERSION


def test_seed_files_are_keyed_as_the_server_keys_them():
    files = sorted(SEED_PRECOMPUTED_DIR.glob("*.whatif.json"))
    if not files:
        pytest.skip("no seed what-ifs computed yet")
    for path in files:
        data = json.loads(path.read_bytes())
        assert data["match_id"] in SITE and path.name == f"{data['match_id']}.whatif.json"
        scenarios = load_precomputed(path, data["version"])
        assert scenarios and all(key == cache_key(data["version"], s.spec) for key, s in scenarios.items())
        assert all(s.status == "completed" and s.spec.pivot_id.startswith(f"{data['match_id']}:")
                   and s.result.baseline_stats is not None for s in scenarios.values())
        if data["version"] != portable_sim_version():
            pytest.xfail(f"{path.name} is for an older simulator ({data['version']}): the server will run its "
                         "chips itself; re-run scripts/make_whatif_fixture.py --match ...")


def test_the_server_reads_a_seed_matchs_file_at_startup(tmp_path, monkeypatch):
    demo_file = precomputed_path(sims.FIXTURE)
    some = next(iter(load_precomputed(demo_file, json.loads(demo_file.read_bytes())["version"]).values()))
    spec = sims.SPECS[0]
    path = tmp_path / f"{spec.match_id}.whatif.json"
    write_precomputed(path, spec.match_id, SIM_VERSION, {"k1": some})
    stale = tmp_path / f"{sims.SPECS[1].match_id}.whatif.json"
    write_precomputed(stale, sims.SPECS[1].match_id, "old-version", {"k2": some})

    async def no_sims(*_, **__):
        return None

    monkeypatch.setenv("PIVOT_SIM_MATCHES", "2")
    monkeypatch.setenv("PIVOT_WHATIF_WARM", "0")
    monkeypatch.setenv("PIVOT_PREWARM_LANGS", "none")
    monkeypatch.setattr(app_module, "load_sims", no_sims)
    monkeypatch.setattr(app_module, "seed_precomputed_path", lambda match_id: tmp_path / f"{match_id}.whatif.json")
    with TestClient(app):
        ahead = app.state.whatif.precomputed
        assert list(ahead[spec.match_id]) == ["k1"]
        assert ahead.get(sims.SPECS[1].match_id) == {}                # made for another version: not used
