"""Finished simulated matches for the local profile, generated once and cached on disk (Ax6).

At startup the API puts `PIVOT_SIM_MATCHES` (default 20, 0 turns it off) matches from `SPECS` into
the store, without holding up startup. Each one is simulated in a worker process the first time,
then written to `PIVOT_DATA_DIR/sims/` (default `./.pivot-data/sims/`):

  M-seed-101.<SIM_VERSION>.json.gz         match, events, minute metrics, pivot candidates, player stats
  M-seed-101.<SIM_VERSION>.frames.json.gz  one tracking frame per second

SIM_VERSION hashes the simulator and analytics source, so editing either re-runs the matches on the
next start; an unchanged one is read straight back. With `PIVOT_SIMS_BACKEND=blob` (Ax15) the disk is a
cache of Azure Blob Storage: a match missing from the disk is downloaded from Blob if Blob has it at this
version, else simulated and written through to Blob (`SimStore`; Blob trouble only means the disk alone). The frames stay on disk; `GET
/api/matches/{id}/frames` reads them from there (`read_frames`). Candidates go on `pivot-candidates`, so the
worker writes the pivots; its message ids are "{match_id}:{minute}", so a second load adds nothing.
Before that, `adapters.results` reads back the pivots the worker wrote for this SIM_VERSION in an
earlier run (Ax10), so the worker skips them instead of calling the model again.

`GET /api/matches` lists them in `SPECS` order, and the site opens the first one (Ax55): a fixed rule,
not a match picked for how it went.

The recorded demo (B02) is stored the same way, from the files committed in `eval/fixtures/`
(`demo-1021.json` and `demo-1021.frames.json.gz`) instead of the cache: `load_fixture`. Its results are keyed by the fixture file's content hash.
It is test data now and only loaded when `PIVOT_DEMO_FIXTURE` asks for it (Ax55).

Each stored match also gets a `Replay`: how it was simulated (match, seed, plants) and the version its
results belong to, so a what-if (A09, `whatif.py`) replays the very same match.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import multiprocessing
import os
import re
import time
from bisect import bisect_left, bisect_right
from collections.abc import Callable
from concurrent.futures import Executor, ProcessPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache, partial
from pathlib import Path

import pivot_core.analytics as analytics_pkg
import pivot_core.sim as sim_pkg
from pivot_adapters import Adapters
from pivot_adapters.local import FilesSimStore, SimStore
from pivot_core.analytics import StatCalculator, detect_candidates, momentum_series, player_match_stats
from pivot_core.domain import Match, MatchEvent, MinuteMetric, PivotCandidate, PlantSpec
from pivot_core.ports import PIVOT_CANDIDATES
from pivot_core.sim import PRESETS, build_demo_match, simulate
from pivot_core.sim.season import load_season, site_matchday, with_prematch
from pivot_core.sim.styles import with_coach_styles

log = logging.getLogger("uvicorn.error")

# 20 matches: on the 2-core server the first start after a simulator change simulates them in about
# 1.5 minutes (6 took ~25 s), the site listing each one as it is ready; later starts read them back
# from PIVOT_DATA_DIR (or Blob) in seconds. To skip that wait, make them on a many-core machine first:
# `uv run scripts/sims_blob.py generate-upload --count 20` (docs/match-data.md).
DEFAULT_MATCHES = 20


@dataclass(frozen=True)
class Replay:
    """How a stored match was simulated, so what-if replays start from the very same match (A09)."""

    version: str                              # the version its results are stored under
    build: Callable[[], Match]                # the match before kick-off
    seed: int | None = None                   # None: the match's own seed
    plants: tuple[PlantSpec, ...] = ()


@dataclass(frozen=True)
class SimSpec:
    seed: int
    home_strength: float
    away_strength: float
    home_formation: str
    away_formation: str

    @property
    def match_id(self) -> str:
        return f"M-seed-{self.seed}"

    def build(self) -> Match:
        """The match before kick-off: the seed's squads, each coach playing a style from the seed (Bx13)."""
        return with_coach_styles(build_demo_match(self.seed, self.home_strength, self.away_strength,
                                                  self.home_formation, self.away_formation))

    def replay(self) -> Replay:
        return Replay(SIM_VERSION, self.build)


SPECS = [
    SimSpec(101, 72, 70, "4-3-3", "4-2-3-1"),
    SimSpec(212, 76, 66, "4-3-3", "4-4-2"),   # 202 hits #130 (a pass ends 0.1 m off the pitch)
    SimSpec(303, 68, 74, "4-4-2", "4-3-3"),
    SimSpec(404, 71, 71, "4-2-3-1", "4-2-3-1"),
    SimSpec(505, 74, 69, "3-5-2", "4-3-3"),
    SimSpec(606, 70, 72, "4-3-3", "3-5-2"),
]


def _source_hash() -> str:
    h = hashlib.sha256()
    for pkg in (sim_pkg, analytics_pkg):
        for path in sorted(Path(pkg.__file__).parent.glob("*.py")):
            h.update(path.name.encode())
            h.update(path.read_bytes())
    return h.hexdigest()[:12]


SIM_VERSION = _source_hash()


def specs_from_env() -> list[SimSpec]:
    """The first `PIVOT_SIM_MATCHES` specs; past the six listed ones, even strengths and seeds 707, 808, ..."""
    return specs_first(int(os.getenv("PIVOT_SIM_MATCHES", str(DEFAULT_MATCHES))))


def specs_first(n: int) -> list[SimSpec]:
    n = max(0, n)
    extra = [SimSpec(101 * k, 70, 70, "4-3-3", "4-4-2") for k in range(len(SPECS) + 1, n + 1)]
    return (SPECS + extra)[:n]


def data_dir_from_env() -> Path:
    return Path(os.getenv("PIVOT_DATA_DIR") or ".pivot-data") / "sims"


def paths(data_dir: Path, spec: SimSpec, version: str = SIM_VERSION) -> tuple[Path, Path]:
    stem = data_dir / f"{spec.match_id}.{version}"
    return stem.with_name(stem.name + ".json.gz"), stem.with_name(stem.name + ".frames.json.gz")


def _write_json_gz(path: Path, data: object) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    tmp.replace(path)                          # a half-written file never looks cached


def build_one(spec: SimSpec, data_dir: Path, version: str = SIM_VERSION) -> bool:
    """Simulate one match and write its files, unless this version is on disk. True if it simulated."""
    data_path, frames_path = paths(data_dir, spec, version)
    if data_path.is_file() and frames_path.is_file():
        return False
    data_dir.mkdir(parents=True, exist_ok=True)
    match = spec.build()
    out = simulate(match)
    events = out.events_as_models()
    frames = out.frames_as_models()
    metrics = momentum_series(match.match_id, events)
    candidates = detect_candidates(match.match_id, metrics, events)
    _write_json_gz(frames_path, [f.model_dump(mode="json") for f in frames])
    _write_json_gz(data_path, {
        "sim_version": version,
        "spec": spec.__dict__,
        "match": prematch(out.match, spec).model_dump(mode="json", round_trip=True),
        "events": [e.model_dump(mode="json", round_trip=True) for e in events],
        "metrics": [m.model_dump(mode="json", round_trip=True) for m in metrics],
        "candidates": [c.model_dump(mode="json", round_trip=True) for c in candidates],
        "player_stats": [p.model_dump(mode="json") for p in player_match_stats(StatCalculator(out.match, events, frames))],
    })
    drop_old_versions(data_dir, spec, version)
    return True


@lru_cache(maxsize=1)
def _season() -> dict | None:
    try:
        return load_season(FIXTURE.parent)
    except OSError:
        log.warning("no season file in %s: simulated matches get only the basic pre-match context", FIXTURE.parent)
        return None


def prematch(match: Match, spec: SimSpec) -> Match:
    """The played match with its pre-match context (Bx13): form, table, head-to-head, news, ties and the
    context effects, from the fictional season up to the round the seed sets it on. Added after the match
    is simulated, so its events and score are the same with or without it."""
    season = _season()
    return match if season is None else with_prematch(match, season, site_matchday(spec.seed))


def drop_old_versions(data_dir: Path, spec: SimSpec, version: str) -> None:
    keep = paths(data_dir, spec, version)
    for old in data_dir.glob(f"{spec.match_id}.*.gz"):
        if old not in keep:
            old.unlink(missing_ok=True)


def _file_ok(path: Path, version: str, match_id: str | None) -> bool:
    """A whole gzip of JSON: the match file also says it is this match at this version."""
    try:
        data = _read_json_gz(path)
    except (OSError, EOFError, ValueError):       # not gzip, cut short, bad CRC, not JSON
        return False
    if match_id is None:
        return isinstance(data, list)
    return (isinstance(data, dict) and data.get("sim_version") == version
            and isinstance(data.get("match"), dict) and data["match"].get("match_id") == match_id
            and all(k in data for k in ("events", "metrics", "candidates")))


async def fetch_from_store(store: SimStore, spec: SimSpec, data_dir: Path, version: str = SIM_VERSION) -> bool:
    """Download this match's two files into the cache, if the store has both whole. True if they are now on disk.

    Each file is written to a temporary name and checked before it is renamed, the frames first, so a
    half-downloaded or corrupt blob never looks cached; it is ignored and the match is simulated.
    """
    data_path, frames_path = paths(data_dir, spec, version)
    tmps = [p.with_name(p.name + ".dl.tmp") for p in (data_path, frames_path)]
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        for src, tmp, match_id in ((data_path, tmps[0], spec.match_id), (frames_path, tmps[1], None)):
            if not await store.download(src.name, tmp):
                return False
            if not await asyncio.to_thread(_file_ok, tmp, version, match_id):
                log.warning("blob %s is corrupt or incomplete; ignoring it and simulating the match", src.name)
                return False
        tmps[1].replace(frames_path)
        tmps[0].replace(data_path)
        await asyncio.to_thread(drop_old_versions, data_dir, spec, version)
        return True
    except Exception:
        log.warning("could not download %s from the store; simulating it instead", spec.match_id, exc_info=True)
        return False
    finally:
        for tmp in tmps:
            tmp.unlink(missing_ok=True)


async def push_to_store(store: SimStore, spec: SimSpec, data_dir: Path, version: str = SIM_VERSION) -> bool:
    """Write the cached files of this match through to the store (frames first, so the match file means both
    are there). False, with a warning, if that did not work: the match is still served from the disk."""
    data_path, frames_path = paths(data_dir, spec, version)
    try:
        for path in (frames_path, data_path):
            await store.upload(path.name, path, version)
        return True
    except Exception:
        log.warning("could not upload %s to the store; it stays on the disk only", spec.match_id, exc_info=True)
        return False


@dataclass
class SimStatus:
    """What `GET /api/sims` reports while the matches load."""

    total: int = 0
    order: list[str] = field(default_factory=list)     # every match id in SPECS order, ready or not
    ready: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    done: bool = True

    def as_dict(self) -> dict:
        return {"total": self.total, "ready": len(self.ready), "failed": len(self.failed),
                "generating": not self.done, "match_ids": list(self.ready)}


async def store_one(adapters: Adapters, data_path: Path) -> str:
    """Put one cached match into the store and its candidates on the worker queue."""
    data = await asyncio.to_thread(_read_json_gz, data_path)
    return await store_data(adapters, data, data.get("sim_version") or SIM_VERSION)


async def store_data(adapters: Adapters, data: dict, version: str) -> str:
    """Store a match file's match, events and metrics, read back the AI's results for this version of
    it, and put its candidates on the worker queue."""
    match = Match.model_validate(data["match"])
    await adapters.matches.upsert_match(match)
    await adapters.matches.append_events([MatchEvent.model_validate(e) for e in data["events"]])
    await adapters.matches.upsert_metrics([MinuteMetric.model_validate(m) for m in data["metrics"]])
    if adapters.results is not None and (known := await adapters.results.open_match(match.match_id, version)):
        log.info("%s: %d pivots read back from earlier runs (results version %s)", match.match_id, known, version)
    for raw in data["candidates"]:
        c = PivotCandidate.model_validate(raw)
        await adapters.queue.send(PIVOT_CANDIDATES, f"{c.match_id}:{c.minute}", c.model_dump(mode="json", round_trip=True))
    return match.match_id


# The recorded demo (B02): committed to the repo, so every machine shows the same match. Tests read it.
FIXTURE = Path(__file__).resolve().parents[4] / "eval" / "fixtures" / "demo-1021.json"


def fixture_from_env() -> Path | None:
    """The recorded demo is off unless asked for (Ax55): `PIVOT_DEMO_FIXTURE=1` loads the committed
    file, a path loads that file; unset or "0" loads none."""
    raw = os.getenv("PIVOT_DEMO_FIXTURE", "")
    if raw in ("", "0"):
        return None
    return FIXTURE if raw == "1" else Path(raw)


async def load_fixture(adapters: Adapters, path: Path,
                       replays: dict[str, Replay] | None = None) -> tuple[str, Path | None]:
    """Store the recorded demo; returns its match id and its frames file (None if it is missing).

    With `replays`, also says there how to replay it, from the preset named in the file.
    """
    raw = await asyncio.to_thread(path.read_bytes)
    data, version = json.loads(raw), "fx-" + hashlib.sha256(raw).hexdigest()[:12]
    match_id = await store_data(adapters, data, version)
    if replays is not None and (replay := fixture_replay(data.get("preset"), version)) is not None:
        replays[match_id] = replay
    frames = path.with_name(path.name.removesuffix(".json") + ".frames.json.gz")
    return match_id, frames if frames.is_file() else None


def fixture_replay(preset: dict | None, version: str) -> Replay | None:
    """The fixture's `preset` block ({name, seed, plants}, written by scripts/make_demo.py) as a Replay."""
    if not preset or preset.get("name") not in PRESETS:
        return None
    seed = int(preset["seed"])
    return Replay(version, partial(PRESETS[preset["name"]].build, seed), seed,
                  tuple(PlantSpec.model_validate(p) for p in preset.get("plants", ())))


def _read_json_gz(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


MATCH_ID = re.compile(r"[A-Za-z0-9_-]+")


def frames_path(data_dir: Path, match_id: str, version: str = SIM_VERSION) -> Path | None:
    """The cached frames file of this match at this version, or None if there is none."""
    if not MATCH_ID.fullmatch(match_id):
        return None
    path = data_dir / f"{match_id}.{version}.frames.json.gz"
    return path if path.is_file() else None


# A whole match is ~6000 frames, ~10 MB of JSON; keep the last two parsed so scrubbing stays cheap.
@lru_cache(maxsize=2)
def _frames(path: Path, mtime_ns: int) -> tuple[list[dict], list[int]]:
    frames = _read_json_gz(path)
    return frames, [f["t"] for f in frames]


def read_frames(path: Path, start: int | None = None, end: int | None = None) -> list[dict]:
    """Frames with start <= t <= end (either bound left out: from kick-off / to the final whistle), in t order."""
    frames, ts = _frames(path, path.stat().st_mtime_ns)
    lo = 0 if start is None else bisect_left(ts, start)
    hi = len(ts) if end is None else bisect_right(ts, end)
    return frames[lo:hi]


def default_executor(n: int) -> Executor:
    # spawn, not fork: the API process already runs threads (uvicorn, to_thread).
    workers = max(1, min(n, int(os.getenv("PIVOT_SIM_WORKERS") or os.cpu_count() or 1)))
    return ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"))


async def _connect_store(store: SimStore | None) -> SimStore | None:
    """The store if it can be used, else None (with a warning): the site never waits on or fails for it."""
    if store is None or isinstance(store, FilesSimStore):
        return None
    try:
        await store.connect()
        return store
    except Exception as exc:
        log.warning("simulated-match store %s unavailable (%r); keeping the matches on the disk only",
                    type(store).__name__, exc)
        try:
            await store.close()
        except Exception:
            pass
        return None


async def load_sims(adapters: Adapters, specs: list[SimSpec], data_dir: Path, status: SimStatus,
                    executor: Executor | None = None, store: SimStore | None = None) -> None:
    """Get every spec's files (disk cache, else the store, else simulated and written through to the store)
    off the event loop and store each match as soon as it is ready."""
    status.total, status.done = len(specs), False
    if not specs:
        status.done = True
        return
    store = await _connect_store(store)
    own = executor is None
    executor = executor or default_executor(len(specs))
    loop = asyncio.get_running_loop()
    started = time.monotonic()

    async def one(spec: SimSpec) -> None:
        try:
            how = "loaded cached"
            if store is not None and not all(p.is_file() for p in paths(data_dir, spec)):
                if await fetch_from_store(store, spec, data_dir):
                    how = "downloaded from the store"
            simulated = await loop.run_in_executor(executor, build_one, spec, data_dir, SIM_VERSION)
            if simulated:
                how = "simulated"
                if store is not None:
                    await push_to_store(store, spec, data_dir)
            await store_one(adapters, paths(data_dir, spec)[0])
            status.ready.append(spec.match_id)
            log.info("%s %s", how, spec.match_id)
        except Exception:
            status.failed.append(spec.match_id)
            log.exception("could not build simulated match %s", spec.match_id)

    try:
        await asyncio.gather(*(one(s) for s in specs))
    finally:
        status.done = True
        if own:
            executor.shutdown(wait=False, cancel_futures=True)
        if store is not None:
            await store.close()
    log.info("simulated matches ready: %d of %d in %.1fs (%s)", len(status.ready), len(specs),
             time.monotonic() - started, data_dir)
