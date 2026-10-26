"""Ax15: simulated matches are kept in a store (Blob) besides the disk; the disk stays the cache the API reads."""

import asyncio
import gzip
import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import pivot_api.app as app_module
from pivot_adapters import build_adapters
from pivot_adapters.azure.fakes import FakeSimStore
from pivot_api import sims
from pivot_api.app import app
from pivot_api.sims import SPECS, SimStatus, load_sims, paths

SPEC = SPECS[0]
names = lambda d: sorted(p.name for p in d.iterdir())   # noqa: E731


@pytest.fixture(scope="module")
def sim_output():
    from pivot_core.sim import build_demo_match, simulate
    return simulate(build_demo_match(SPEC.seed, SPEC.home_strength, SPEC.away_strength,
                                     SPEC.home_formation, SPEC.away_formation))


@pytest.fixture
def calls(monkeypatch, sim_output):
    counter = {"n": 0}

    def fake_simulate(match):
        counter["n"] += 1
        return sim_output

    monkeypatch.setattr(sims, "simulate", fake_simulate)
    return counter


def load(store, data_dir, specs=(SPEC,)):
    status = SimStatus()
    with ThreadPoolExecutor(1) as pool:
        asyncio.run(load_sims(build_adapters("local"), list(specs), data_dir, status, executor=pool, store=store))
    return status


def test_cold_start_generates_and_uploads_then_an_empty_cache_downloads_without_simulating(tmp_path, calls):
    store = FakeSimStore()
    assert load(store, tmp_path / "a").ready == [SPEC.match_id]
    data_name, frames_name = (p.name for p in paths(tmp_path / "a", SPEC))
    assert calls["n"] == 1 and sorted(store.blobs) == sorted([data_name, frames_name])
    assert store.versions[data_name] == sims.SIM_VERSION and store.calls["close"] == 1

    status = load(store, tmp_path / "b")                      # a new server: empty disk, same Blob
    assert status.ready == [SPEC.match_id] and calls["n"] == 1 and store.calls["upload"] == 2
    assert names(tmp_path / "b") == sorted([data_name, frames_name])   # whole files, no temp leftovers
    assert (tmp_path / "b" / frames_name).read_bytes() == store.blobs[frames_name]


def test_a_warm_cache_does_not_touch_the_store(tmp_path, calls):
    store = FakeSimStore()
    load(store, tmp_path)
    before = store.calls["download"]
    load(store, tmp_path)
    assert store.calls["download"] == before and calls["n"] == 1


def test_blobs_of_another_sim_version_are_ignored(tmp_path, calls):
    store = FakeSimStore()
    load(store, tmp_path / "a")
    old = {n.replace(sims.SIM_VERSION, "0ldversion00"): b for n, b in store.blobs.items()}
    store.blobs = dict(old)                                   # Blob only has what an older simulator made
    status = load(store, tmp_path / "b")
    assert status.ready == [SPEC.match_id] and calls["n"] == 2
    assert set(store.blobs) == set(old) | {p.name for p in paths(tmp_path / "b", SPEC)}


@pytest.mark.parametrize("damage", ["garbage", "cut", "wrong_version", "missing_frames"])
def test_a_corrupt_or_partial_blob_is_ignored_and_regenerated(tmp_path, calls, damage):
    store = FakeSimStore()
    load(store, tmp_path / "a")
    data_name, frames_name = (p.name for p in paths(tmp_path / "a", SPEC))
    if damage == "garbage":
        store.blobs[frames_name] = b"not gzip at all"
    elif damage == "cut":
        store.blobs[data_name] = store.blobs[data_name][: len(store.blobs[data_name]) // 2]
    elif damage == "wrong_version":
        store.blobs[data_name] = gzip.compress(b'{"sim_version":"other","match":{"match_id":"M-seed-101"}}')
    else:
        del store.blobs[frames_name]
    status = load(store, tmp_path / "b")
    assert status.ready == [SPEC.match_id] and status.failed == [] and calls["n"] == 2
    assert not any(n.endswith(".tmp") for n in names(tmp_path / "b"))
    again = FakeSimStore()
    again.blobs = dict(store.blobs)
    load(again, tmp_path / "c")                               # the good files went back up
    assert calls["n"] == 2


def test_an_unreachable_store_falls_back_to_the_disk(tmp_path, calls):
    store = FakeSimStore(unreachable=True)
    status = load(store, tmp_path)
    assert status.ready == [SPEC.match_id] and calls["n"] == 1 and store.calls["upload"] == 0
    assert all(p.is_file() for p in paths(tmp_path, SPEC))


def test_an_upload_that_fails_midway_still_serves_from_the_disk(tmp_path, calls):
    class Failing(FakeSimStore):
        async def upload(self, name, src, version):
            raise OSError("network down")

    status = load(Failing(), tmp_path)
    assert status.ready == [SPEC.match_id] and status.failed == []


def test_the_site_still_serves_when_blob_is_unreachable(tmp_path, monkeypatch, calls):
    monkeypatch.setenv("PIVOT_SIM_MATCHES", "1")
    monkeypatch.setenv("PIVOT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sims, "default_executor", lambda n: ThreadPoolExecutor(1))
    monkeypatch.setattr(app_module, "build_sim_store", lambda: FakeSimStore(unreachable=True))
    with TestClient(app) as client:
        for _ in range(500):
            if not client.get("/api/sims").json()["generating"]:
                break
            client.portal.call(asyncio.sleep, 0.02)
        assert client.get("/api/sims").json()["ready"] == 1
        assert client.get(f"/api/matches/{SPEC.match_id}/frames", params={"to": 2}).status_code == 200


def test_the_frames_endpoint_serves_a_match_that_was_downloaded(tmp_path, monkeypatch, calls):
    store = FakeSimStore()
    load(store, tmp_path / "other")
    n = calls["n"]
    monkeypatch.setenv("PIVOT_SIM_MATCHES", "1")
    monkeypatch.setenv("PIVOT_DATA_DIR", str(tmp_path / "fresh"))
    monkeypatch.setattr(sims, "default_executor", lambda n: ThreadPoolExecutor(1))
    monkeypatch.setattr(app_module, "build_sim_store", lambda: store)
    with TestClient(app) as client:
        for _ in range(500):
            if not client.get("/api/sims").json()["generating"]:
                break
            client.portal.call(asyncio.sleep, 0.02)
        frames = client.get(f"/api/matches/{SPEC.match_id}/frames", params={"to": 2}).json()
        assert [f["t"] for f in frames] == [0, 1, 2]
    assert calls["n"] == n


def test_backend_setting(monkeypatch):
    from pivot_adapters import build_sim_store
    from pivot_adapters.azure.blob import BlobSimStore
    from pivot_adapters.local import FilesSimStore
    monkeypatch.delenv("PIVOT_SIMS_BACKEND", raising=False)
    assert isinstance(build_sim_store(), FilesSimStore)
    monkeypatch.setenv("PIVOT_SIMS_BACKEND", "blob")
    monkeypatch.setenv("PIVOT_BLOB_ENDPOINT", "https://x.blob.core.windows.net/")
    store = build_sim_store()
    assert isinstance(store, BlobSimStore) and store.container == "sims" and store.account == "x"
    monkeypatch.setenv("PIVOT_BLOB_CONTAINER", "mine")
    assert build_sim_store().container == "mine"
    monkeypatch.setenv("PIVOT_SIMS_BACKEND", "nope")
    with pytest.raises(ValueError):
        build_sim_store()


def test_files_backend_without_an_endpoint_is_a_no_op(tmp_path, calls):
    from pivot_adapters import build_sim_store
    assert load(build_sim_store(), tmp_path).ready == [SPEC.match_id] and calls["n"] == 1


# --- scripts/sims_blob.py

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "sims_blob.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("sims_blob", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def args(script, *argv):
    return script.parser().parse_args(list(argv))


@pytest.fixture
def work(tmp_path, monkeypatch):
    monkeypatch.setattr(sims, "default_executor", lambda n: ThreadPoolExecutor(1))
    return tmp_path / "work"


def test_script_generate_upload_skips_what_blob_has(script, work, calls, capsys):
    store = FakeSimStore()
    run = lambda *a: asyncio.run(script.run(args(script, "generate-upload", "--work-dir", str(work), *a), store))  # noqa: E731
    assert run("--seeds", "101") == 0
    out = capsys.readouterr().out
    assert sims.SIM_VERSION in out and "作废" in out and "MB" in out
    assert calls["n"] == 1 and len(store.blobs) == 2
    assert run("--seeds", "101") == 0                       # already in Blob at this version
    assert "跳过" in capsys.readouterr().out and calls["n"] == 1 and store.calls["upload"] == 2
    assert run("--seeds", "101", "--force") == 0 and store.calls["upload"] == 4
    assert str(work.resolve().parent) not in str(Path(__file__).resolve().parents[3])   # never inside the repo


def test_script_count_follows_the_sim_matches_rule(script):
    assert [s.seed for s in script.pick_specs(8, None)][-2:] == [707, 808]
    assert len(script.pick_specs(None, None)) == 6
    assert [s.seed for s in script.pick_specs(None, [212, 999])] == [212, 999]


def test_script_list_and_clean_with_a_dry_run_first(script, work, calls, capsys):
    store = FakeSimStore()
    store.blobs.update({"M-seed-101.oldversion1.json.gz": b"x" * 10, "M-seed-101.oldversion1.frames.json.gz": b"y" * 20})
    asyncio.run(script.run(args(script, "generate-upload", "--work-dir", str(work), "--seeds", "101"), store))
    capsys.readouterr()

    assert asyncio.run(script.run(args(script, "list"), store)) == 0
    out = capsys.readouterr().out
    assert "当前版本" in out and "oldversion1" in out and "1 场完整" in out

    asyncio.run(script.run(args(script, "clean"), store))              # dry run by default
    out = capsys.readouterr().out
    assert "演练" in out and "--yes-delete" in out and len(store.blobs) == 4

    asyncio.run(script.run(args(script, "clean", "--yes-delete"), store))
    assert sorted(store.blobs) == sorted(p.name for p in paths(work, SPEC))
    assert "已删除" in capsys.readouterr().out


def test_script_reports_an_unreachable_blob(script, capsys):
    assert asyncio.run(script.run(args(script, "list"), FakeSimStore(unreachable=True))) == 2
    assert "连不上" in capsys.readouterr().err


# --- the real account: PIVOT_BLOB_IT=1 PIVOT_BLOB_ENDPOINT=https://<account>.blob.core.windows.net/

@pytest.mark.skipif(os.getenv("PIVOT_BLOB_IT") != "1", reason="set PIVOT_BLOB_IT=1 to use the real storage account")
def test_real_blob_round_trip(tmp_path, calls):
    from azure.identity.aio import DefaultAzureCredential
    from azure.storage.blob.aio import BlobServiceClient

    from pivot_adapters.azure.blob import BlobSimStore

    endpoint = os.environ["PIVOT_BLOB_ENDPOINT"]
    container = "sims-it-ax15"

    async def run():
        store = BlobSimStore(endpoint, container)
        try:
            await store.connect()                              # creates the throwaway container
            status = SimStatus()
            with ThreadPoolExecutor(1) as pool:
                await load_sims(build_adapters("local"), [SPEC], tmp_path / "a", status, executor=pool, store=store)
            assert calls["n"] == 1
            store2 = BlobSimStore(endpoint, container)
            with ThreadPoolExecutor(1) as pool:
                await load_sims(build_adapters("local"), [SPEC], tmp_path / "b", SimStatus(), executor=pool, store=store2)
            assert calls["n"] == 1 and all(p.is_file() for p in paths(tmp_path / "b", SPEC))
            store3 = BlobSimStore(endpoint, container)
            await store3.connect()
            assert len(await store3.list()) == 2
            await store3.delete([b.name for b in await store3.list()])
            assert await store3.list() == []
            await store3.close()
        finally:
            credential = DefaultAzureCredential()
            service = BlobServiceClient(endpoint, credential=credential)
            try:
                await service.delete_container(container)
            finally:
                await service.close()
                await credential.close()

    asyncio.run(run())
