"""The AI's results on disk for the local profile: pivots, personalised narratives and agent traces (Ax10).

Reads still come from the in-memory repositories. On top of them, every pivot, narrative version
and trace of an *opened* match is also written to its own JSON file, and opening the match again
after a restart reads them back, so the worker skips those candidates and makes no model call:

  <root>/<match_id>/<version>/pivots/<pivot_id>.json
  <root>/<match_id>/<version>/narratives/<pivot_id>.<prefs hash>.json
  <root>/<match_id>/<version>/traces/<trace_id>.json

`version` names the source data the results were written from (the simulator version, the
fixture's content hash), plus the optional tag; opening a match at a new version starts empty
and removes the other versions of that match. Matches never opened (the hand-made demo, the
worker's --demo) stay in memory only. Files are written whole to a temp file and renamed; one
that cannot be read is logged and skipped, and a failed write is logged and the result kept in memory.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel

from pivot_core.domain import AgentTrace, Narrative, Pivot

from .store import InMemoryMatchRepository, InMemoryTraceRepository

log = logging.getLogger("pivot_adapters.results")


def _name(id_: str) -> str:
    return quote(id_, safe="-_")              # "M-seed-101:p63" -> "M-seed-101%3Ap63", reversible and path-safe


class ResultFiles:
    """Owns the result folder, and the two repositories that write into it."""

    def __init__(self, root: Path, tag: str = "") -> None:
        self.root = root
        self.tag = tag
        self._dirs: dict[str, Path] = {}      # match_id -> folder of its opened version
        self.matches = FileBackedMatchRepository(self)
        self.traces = FileBackedTraceRepository(self)

    async def open_match(self, match_id: str, version: str) -> int:
        """Read back what was stored for this version of the match and keep storing there. Returns the pivot count."""
        key = f"{version}-{self.tag}" if self.tag else version
        folder = self.root / _name(match_id) / _name(key)
        pivots, narratives, traces = await asyncio.to_thread(self._read, folder)
        for pivot in pivots:
            await InMemoryMatchRepository.upsert_pivot(self.matches, pivot)
        for pivot_id, narrative in narratives:
            await InMemoryMatchRepository.upsert_narrative(self.matches, match_id, pivot_id, narrative)
        for trace in traces:
            await InMemoryTraceRepository.append_trace(self.traces, trace)
        self._dirs[match_id] = folder
        try:                                  # results of other versions of this match are never read again
            for old in folder.parent.iterdir() if folder.parent.is_dir() else ():
                if old != folder and old.is_dir():
                    shutil.rmtree(old, ignore_errors=True)
        except OSError:
            log.warning("could not clear old results of %s", match_id, exc_info=True)
        log.debug("%s: read back %d pivots, %d narratives, %d traces from %s", match_id, len(pivots),
                  len(narratives), len(traces), folder)
        return len(pivots)

    def write(self, match_id: str, kind: str, name: str, data: dict) -> None:
        folder = self._dirs.get(match_id)
        if folder is None:
            return
        path = folder / kind / f"{name}.json"
        tmp = path.with_name(path.name + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, path)             # a half-written file never replaces a good one
        except OSError:
            log.warning("could not write %s; kept in memory only", path, exc_info=True)

    def _read(self, folder: Path) -> tuple[list[Pivot], list[tuple[str, Narrative]], list[AgentTrace]]:
        return (_parse(folder / "pivots", Pivot.model_validate),
                _parse(folder / "narratives", lambda d: (d["pivot_id"], Narrative.model_validate(d["narrative"]))),
                _parse(folder / "traces", AgentTrace.model_validate))


def _parse[T](folder: Path, parse: Callable[[Any], T]) -> list[T]:
    out = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else ():
        try:
            out.append(parse(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError, KeyError, TypeError) as exc:   # ValidationError is a ValueError
            log.warning("skipping unreadable result file %s: %s", path, exc)
    return out


def _dump(model: BaseModel) -> dict:
    return model.model_dump(mode="json", round_trip=True)


class FileBackedMatchRepository(InMemoryMatchRepository):
    """In-memory match data; pivots and narrative versions of opened matches are also written to disk."""

    def __init__(self, files: ResultFiles) -> None:
        super().__init__()
        self._files = files

    async def upsert_pivot(self, pivot: Pivot) -> None:
        await super().upsert_pivot(pivot)
        self._files.write(pivot.match_id, "pivots", _name(pivot.pivot_id), _dump(pivot))

    async def upsert_narrative(self, match_id: str, pivot_id: str, narrative: Narrative) -> None:
        await super().upsert_narrative(match_id, pivot_id, narrative)
        prefs = hashlib.sha256(narrative.prefs.model_dump_json().encode()).hexdigest()[:12]
        self._files.write(match_id, "narratives", f"{_name(pivot_id)}.{prefs}",
                          {"pivot_id": pivot_id, "narrative": _dump(narrative)})


class FileBackedTraceRepository(InMemoryTraceRepository):
    """In-memory traces; those of opened matches are also written to disk."""

    def __init__(self, files: ResultFiles) -> None:
        super().__init__()
        self._files = files

    async def append_trace(self, trace: AgentTrace) -> None:
        await super().append_trace(trace)
        self._files.write(trace.match_id, "traces", _name(trace.trace_id), _dump(trace))
