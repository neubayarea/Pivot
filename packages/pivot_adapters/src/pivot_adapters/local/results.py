"""The AI's results kept across restarts: pivots, personalised narratives, agent traces and what-ifs (Ax10, A09).

Reads still come from the in-memory repositories. On top of them, every pivot, narrative version
and trace of an *opened* match is also written to a backend, and opening the match again after a
restart reads them back, so the worker skips those candidates and makes no model call. The backend
is a folder on disk here (`ResultFiles`), or Cosmos DB (`pivot_adapters.azure.cosmos`, Ax11):

  <root>/<match_id>/<version>/pivots/<pivot_id>.json
  <root>/<match_id>/<version>/narratives/<pivot_id>.<prefs hash>.json
  <root>/<match_id>/<version>/traces/<trace_id>.json
  <root>/<match_id>/<version>/scenarios/<cache key>.json   finished what-if scenarios (A09)

`version` names the source data the results were written from (the simulator version, the
fixture's content hash), plus the optional tag; opening a match at a new version starts empty
and removes the other versions of that match. Matches never opened (the hand-made demo, the
worker's --demo) stay in memory only. Files are written whole to a temp file and renamed; one
that cannot be read is logged and skipped, and a failed write is logged and the result kept in memory.

Only what the model actually produced is served again: a pivot that fell back to the template
because a call failed (`fell_back`), with its traces and narrative versions, and every template
narrative version, are dropped on read-back and deleted from the backend, so that start asks the model again.
A finished what-if scenario is kept whole, with the traces of its chain: the replays are the costly part,
and the API writes its comparison again itself if it came from the template.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
from collections import defaultdict
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

from pydantic import BaseModel

from pivot_core.domain import AgentTrace, Narrative, Pivot, Scenario

from .store import InMemoryMatchRepository, InMemoryTraceRepository

log = logging.getLogger("pivot_adapters.results")

KINDS = ("pivots", "narratives", "traces", "scenarios")
Stored = dict[str, list[tuple[str, Any]]]     # kind -> (backend's handle on the item, its JSON), in name order


def _name(id_: str) -> str:
    return quote(id_, safe="-_")              # "M-seed-101:p63" -> "M-seed-101%3Ap63", reversible and path-safe


class ResultBackend(Protocol):
    """Where a `ResultStore` keeps the JSON of each result. `key` is the match's version plus the tag."""

    async def connect(self) -> None:
        """Check the backend can be used; raising makes the store use its fallback instead."""

    async def load(self, match_id: str, key: str) -> Stored:
        """Everything stored for this version of the match; the other versions of it are deleted."""

    async def delete(self, match_id: str, key: str, handles: list[str]) -> None: ...

    async def write(self, match_id: str, key: str, kind: str, name: str, data: dict) -> None:
        """Store one result, replacing the one of the same name. Logs and returns on failure."""

    async def close(self) -> None: ...


class ResultStore:
    """The two repositories that write into a backend, and the read-back of an opened match."""

    def __init__(self, backend: ResultBackend, tag: str = "", fallback: ResultBackend | None = None) -> None:
        self.backend = backend
        self.tag = tag
        self._fallback = fallback             # used instead when `backend` cannot connect
        self._connected = False
        self._lock = asyncio.Lock()
        self._keys: dict[str, str] = {}       # match_id -> its opened version
        self._scenarios: dict[str, dict[str, Scenario]] = {}   # match_id -> cache key -> finished scenario
        self.matches = StoredMatchRepository(self)
        self.traces = StoredTraceRepository(self)

    async def open_match(self, match_id: str, version: str) -> int:
        """Read back what was stored for this version of the match and keep storing there. Returns the pivot count."""
        await self._connect()
        key = f"{version}-{self.tag}" if self.tag else version
        try:
            stored = await self.backend.load(match_id, key)
        except Exception:                     # a store that cannot be read must not stop the match
            log.warning("could not read back the results of %s; the model writes them again", match_id,
                        exc_info=True)
            stored = {}
        scenarios = _parse(match_id, stored.get("scenarios", ()),
                           lambda d: (str(d["key"]), Scenario.model_validate(d["scenario"])))
        pivots, narratives, traces, drop = keep(match_id, stored, {s.scenario_id for _, (_, s) in scenarios})
        if drop:
            log.info("%s: %d stored results fell back without the model; written again this run", match_id, len(drop))
            try:
                await self.backend.delete(match_id, key, drop)
            except Exception:
                log.warning("could not remove dropped results of %s", match_id, exc_info=True)
        for pivot in pivots:
            await InMemoryMatchRepository.upsert_pivot(self.matches, pivot)
        for pivot_id, narrative in narratives:
            await InMemoryMatchRepository.upsert_narrative(self.matches, match_id, pivot_id, narrative)
        for trace in traces:
            await InMemoryTraceRepository.append_trace(self.traces, trace)
        self._scenarios[match_id] = dict(s for _, s in scenarios)
        self._keys[match_id] = key
        log.debug("%s: read back %d pivots, %d narratives, %d traces", match_id, len(pivots), len(narratives),
                  len(traces))
        return len(pivots)

    def scenarios(self, match_id: str) -> dict[str, Scenario]:
        """Finished what-if scenarios of an opened match, by the cache key they were stored under."""
        return dict(self._scenarios.get(match_id, {}))

    async def store_scenario(self, match_id: str, key: str, scenario: Scenario) -> None:
        if match_id not in self._keys:
            return
        self._scenarios.setdefault(match_id, {})[key] = scenario
        await self.write(match_id, "scenarios", _name(key), {"key": key, "scenario": _dump(scenario)})

    async def write(self, match_id: str, kind: str, name: str, data: dict) -> None:
        key = self._keys.get(match_id)
        if key is not None:
            await self.backend.write(match_id, key, kind, name, data)

    async def close(self) -> None:
        await self.backend.close()

    async def _connect(self) -> None:
        async with self._lock:
            if self._connected:
                return
            self._connected = True
            try:
                await self.backend.connect()
            except Exception as exc:          # the site starts whatever the store does
                if self._fallback is None:
                    raise
                log.warning("results backend %s unavailable (%s); keeping the AI's results on disk instead",
                            type(self.backend).__name__, exc)
                self.backend = self._fallback
                await self.backend.connect()


def keep(match_id: str, stored: Stored, scenario_ids: Collection[str] = ()
         ) -> tuple[list[Pivot], list[tuple[str, Narrative]], list[AgentTrace], list[str]]:
    """What is worth serving again, and the handles of everything else, which the backend deletes.

    Traces of the what-if scenarios in `scenario_ids` are kept along with them.
    """
    pivots = _parse(match_id, stored.get("pivots", ()), Pivot.model_validate)
    narratives = _parse(match_id, stored.get("narratives", ()),
                        lambda d: (d["pivot_id"], Narrative.model_validate(d["narrative"])))
    traces = _parse(match_id, stored.get("traces", ()), AgentTrace.model_validate)
    chains: defaultdict[str | None, list[AgentTrace]] = defaultdict(list)
    for _, t in sorted(traces, key=lambda ht: ht[1].step):
        chains[t.chain_id].append(t)
    kept = {p.pivot_id for _, p in pivots if not fell_back(p, chains[p.chain_id])}
    drop = [h for h, p in pivots if p.pivot_id not in kept]
    drop += [h for h, (pivot_id, n) in narratives if pivot_id not in kept or n.source != "llm"]
    drop += [h for h, t in traces if t.input_ref not in kept and t.input_ref not in scenario_ids]
    dropped = set(drop)
    return ([p for h, p in pivots if h not in dropped],
            [n for h, n in narratives if h not in dropped],
            [t for h, t in traces if h not in dropped],
            drop)


def fell_back(pivot: Pivot, chain: list[AgentTrace]) -> bool:
    """True if the pivot holds template text only because a step failed (no model, a timeout, a 429, an error).

    A degraded pivot is a real result only when the step before the template was the Verifier
    rejecting the model's last draft: the model answered, its drafts just did not pass. Any other
    way to the template (Judge unavailable, Explainer or Verifier error, the workflow failing)
    is tried again on the next start. Confirmed and rejected pivots come from the model.
    """
    if pivot.status != "degraded":
        return False
    before = [t for t in chain if t.agent != "template"]
    return not (before and before[-1].agent == "verifier" and before[-1].status == "rejected")


def _parse[T](match_id: str, items, parse: Callable[[Any], T]) -> list[tuple[str, T]]:
    out = []
    for handle, data in items:
        try:
            out.append((handle, parse(data)))
        except (ValueError, KeyError, TypeError) as exc:   # ValidationError is a ValueError
            log.warning("%s: skipping unreadable result %s: %s", match_id, handle, exc)
    return out


def _dump(model: BaseModel) -> dict:
    return model.model_dump(mode="json", round_trip=True)


class ResultFiles(ResultStore):
    """The results of opened matches as JSON files under `root`."""

    def __init__(self, root: Path, tag: str = "") -> None:
        super().__init__(FileResults(root), tag)
        self.root = root


class FileResults:
    """`ResultBackend` on a folder: one JSON file per result, one folder per match and version."""

    def __init__(self, root: Path) -> None:
        self.root = root

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    def _folder(self, match_id: str, key: str) -> Path:
        return self.root / _name(match_id) / _name(key)

    async def load(self, match_id: str, key: str) -> Stored:
        return await asyncio.to_thread(self._load, self._folder(match_id, key))

    def _load(self, folder: Path) -> Stored:
        stored: Stored = {kind: [] for kind in KINDS}
        for kind in KINDS:
            for path in sorted((folder / kind).glob("*.json")) if (folder / kind).is_dir() else ():
                try:
                    stored[kind].append((str(path), json.loads(path.read_text(encoding="utf-8"))))
                except (OSError, ValueError) as exc:
                    log.warning("skipping unreadable result file %s: %s", path, exc)
        try:                                  # results of other versions of this match are never read again
            for old in folder.parent.iterdir() if folder.parent.is_dir() else ():
                if old != folder and old.is_dir():
                    shutil.rmtree(old, ignore_errors=True)
        except OSError:
            log.warning("could not clear old results in %s", folder.parent, exc_info=True)
        return stored

    async def delete(self, match_id: str, key: str, handles: list[str]) -> None:
        for path in handles:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                log.warning("could not remove %s", path, exc_info=True)

    async def write(self, match_id: str, key: str, kind: str, name: str, data: dict) -> None:
        path = self._folder(match_id, key) / kind / f"{name}.json"
        tmp = path.with_name(path.name + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, path)             # a half-written file never replaces a good one
        except OSError:
            log.warning("could not write %s; kept in memory only", path, exc_info=True)


class StoredMatchRepository(InMemoryMatchRepository):
    """In-memory match data; pivots and narrative versions of opened matches are also stored."""

    def __init__(self, store: ResultStore) -> None:
        super().__init__()
        self._store = store

    async def upsert_pivot(self, pivot: Pivot) -> None:
        await super().upsert_pivot(pivot)
        await self._store.write(pivot.match_id, "pivots", _name(pivot.pivot_id), _dump(pivot))

    async def upsert_narrative(self, match_id: str, pivot_id: str, narrative: Narrative) -> None:
        await super().upsert_narrative(match_id, pivot_id, narrative)
        if narrative.source != "llm":         # a template version is free to write again, and the model may do better
            return
        prefs = hashlib.sha256(narrative.prefs.model_dump_json().encode()).hexdigest()[:12]
        await self._store.write(match_id, "narratives", f"{_name(pivot_id)}.{prefs}",
                                {"pivot_id": pivot_id, "narrative": _dump(narrative)})


class StoredTraceRepository(InMemoryTraceRepository):
    """In-memory traces; those of opened matches are also stored."""

    def __init__(self, store: ResultStore) -> None:
        super().__init__()
        self._store = store

    async def append_trace(self, trace: AgentTrace) -> None:
        await super().append_trace(trace)
        await self._store.write(trace.match_id, "traces", _name(trace.trace_id), _dump(trace))

