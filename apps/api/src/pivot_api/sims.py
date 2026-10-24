"""Finished simulated matches for the local profile, generated once and cached on disk (Ax6).

At startup the API puts `PIVOT_SIM_MATCHES` (default 6, 0 turns it off) matches from `SPECS` into
the store, without holding up startup. Each one is simulated in a worker process the first time,
then written to `PIVOT_DATA_DIR/sims/` (default `./.pivot-data/sims/`):

  M-seed-101.<SIM_VERSION>.json.gz         match, events, minute metrics, pivot candidates, player stats
  M-seed-101.<SIM_VERSION>.frames.json.gz  one tracking frame per second

SIM_VERSION hashes the simulator and analytics source, so editing either re-runs the matches on the
next start; an unchanged one is read straight back. The frames stay on disk; `GET
/api/matches/{id}/frames` reads them from there (`read_frames`). Candidates go on `pivot-candidates`, so the
worker writes the pivots; its message ids are "{match_id}:{minute}", so a second load adds nothing.
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
from concurrent.futures import Executor, ProcessPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pivot_core.analytics as analytics_pkg
import pivot_core.sim as sim_pkg
from pivot_adapters import Adapters
from pivot_core.analytics import StatCalculator, detect_candidates, momentum_series, player_match_stats
from pivot_core.domain import Match, MatchEvent, MinuteMetric, PivotCandidate
from pivot_core.ports import PIVOT_CANDIDATES
from pivot_core.sim import build_demo_match, simulate

log = logging.getLogger("uvicorn.error")

DEFAULT_MATCHES = 6


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
    n = max(0, int(os.getenv("PIVOT_SIM_MATCHES", str(DEFAULT_MATCHES))))
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
    match = build_demo_match(spec.seed, spec.home_strength, spec.away_strength, spec.home_formation,
                             spec.away_formation)
    out = simulate(match)
    events = out.events_as_models()
    frames = out.frames_as_models()
    metrics = momentum_series(match.match_id, events)
    candidates = detect_candidates(match.match_id, metrics, events)
    _write_json_gz(frames_path, [f.model_dump(mode="json") for f in frames])
    _write_json_gz(data_path, {
        "sim_version": version,
        "spec": spec.__dict__,
        "match": out.match.model_dump(mode="json", round_trip=True),
        "events": [e.model_dump(mode="json", round_trip=True) for e in events],
        "metrics": [m.model_dump(mode="json", round_trip=True) for m in metrics],
        "candidates": [c.model_dump(mode="json", round_trip=True) for c in candidates],
        "player_stats": [p.model_dump(mode="json") for p in player_match_stats(StatCalculator(out.match, events, frames))],
    })
    for old in data_dir.glob(f"{spec.match_id}.*.gz"):  # older versions of this match
        if old not in (data_path, frames_path):
            old.unlink(missing_ok=True)
    return True


@dataclass
class SimStatus:
    """What `GET /api/sims` reports while the matches load."""

    total: int = 0
    ready: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    done: bool = True

    def as_dict(self) -> dict:
        return {"total": self.total, "ready": len(self.ready), "failed": len(self.failed),
                "generating": not self.done, "match_ids": list(self.ready)}


async def store_one(adapters: Adapters, data_path: Path) -> str:
    """Put one cached match into the store and its candidates on the worker queue."""
    data = await asyncio.to_thread(_read_json_gz, data_path)
    match = Match.model_validate(data["match"])
    await adapters.matches.upsert_match(match)
    await adapters.matches.append_events([MatchEvent.model_validate(e) for e in data["events"]])
    await adapters.matches.upsert_metrics([MinuteMetric.model_validate(m) for m in data["metrics"]])
    for raw in data["candidates"]:
        c = PivotCandidate.model_validate(raw)
        await adapters.queue.send(PIVOT_CANDIDATES, f"{c.match_id}:{c.minute}", c.model_dump(mode="json", round_trip=True))
    return match.match_id


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


async def load_sims(adapters: Adapters, specs: list[SimSpec], data_dir: Path, status: SimStatus,
                    executor: Executor | None = None) -> None:
    """Build (or reuse) every spec's files off the event loop and store each match as soon as it is ready."""
    status.total, status.done = len(specs), False
    if not specs:
        status.done = True
        return
    own = executor is None
    executor = executor or default_executor(len(specs))
    loop = asyncio.get_running_loop()
    started = time.monotonic()

    async def one(spec: SimSpec) -> None:
        try:
            simulated = await loop.run_in_executor(executor, build_one, spec, data_dir, SIM_VERSION)
            await store_one(adapters, paths(data_dir, spec)[0])
            status.ready.append(spec.match_id)
            log.info("%s %s", "simulated" if simulated else "loaded cached", spec.match_id)
        except Exception:
            status.failed.append(spec.match_id)
            log.exception("could not build simulated match %s", spec.match_id)

    try:
        await asyncio.gather(*(one(s) for s in specs))
    finally:
        status.done = True
        if own:
            executor.shutdown(wait=False, cancel_futures=True)
    log.info("simulated matches ready: %d of %d in %.1fs (%s)", len(status.ready), len(specs),
             time.monotonic() - started, data_dir)
