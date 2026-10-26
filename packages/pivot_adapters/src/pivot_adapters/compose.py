"""Composition root: pick the adapter set for the deployment profile (ADR-0001).

`PIVOT_PROFILE` is `local` (default), `c1` or `c2`. Only `local` exists so far; the Azure
adapters for c1/c2 come with A08.

Local keeps the AI's results under `PIVOT_DATA_DIR/results/` (default `./.pivot-data`) so a restart
reads them back instead of calling the model again (Ax10). `PIVOT_RESULTS=0` keeps them in memory only;
`PIVOT_RESULTS_TAG` is added to every match's version, so changing it writes everything again.
`PIVOT_RESULTS_BACKEND=cosmos` keeps them in Cosmos DB instead (`PIVOT_COSMOS_ENDPOINT`,
`PIVOT_COSMOS_DATABASE`, Ax11), and on disk after all if Cosmos cannot be reached at startup.
`build_sim_store` picks where finished simulated matches are kept besides the disk (`PIVOT_SIMS_BACKEND`, Ax15).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pivot_core.ports import LiveNegotiator, LivePublisher, MatchRepository, ResultCache, TraceRepository, WorkQueue

PROFILES = ("local", "c1", "c2")


@dataclass(frozen=True)
class Adapters:
    profile: str
    queue: WorkQueue
    matches: MatchRepository
    traces: TraceRepository
    live: LivePublisher
    negotiator: LiveNegotiator
    results: ResultCache | None = None        # None: results live as long as the process


def build_adapters(profile: str | None = None) -> Adapters:
    profile = (profile or os.getenv("PIVOT_PROFILE") or "local").strip().lower()
    if profile == "local":
        from .local import (
            FileResults,
            InMemoryLivePublisher,
            InMemoryMatchRepository,
            InMemoryTraceRepository,
            InMemoryWorkQueue,
            LocalNegotiator,
            ResultFiles,
            ResultStore,
        )

        if os.getenv("PIVOT_RESULTS", "1") == "0":
            results, matches, traces = None, InMemoryMatchRepository(), InMemoryTraceRepository()
        else:
            root = Path(os.getenv("PIVOT_DATA_DIR") or ".pivot-data") / "results"
            tag = os.getenv("PIVOT_RESULTS_TAG", "").strip()
            backend = (os.getenv("PIVOT_RESULTS_BACKEND") or "files").strip().lower()
            if backend == "cosmos":
                from .azure.cosmos import CosmosResults

                results = ResultStore(CosmosResults.from_env(), tag, fallback=FileResults(root))
            elif backend == "files":
                results = ResultFiles(root, tag)
            else:
                raise ValueError(f"unknown PIVOT_RESULTS_BACKEND {backend!r}; expected files or cosmos")
            matches, traces = results.matches, results.traces
        return Adapters(
            profile=profile,
            queue=InMemoryWorkQueue(),
            matches=matches,
            traces=traces,
            live=InMemoryLivePublisher(),
            negotiator=LocalNegotiator(),
            results=results,
        )
    if profile in PROFILES:
        raise NotImplementedError(f"PIVOT_PROFILE={profile!r}: Azure adapters are not implemented yet (A08)")
    raise ValueError(f"unknown PIVOT_PROFILE {profile!r}; expected one of {', '.join(PROFILES)}")


def build_sim_store():
    """Where simulated matches are kept besides the disk, from `PIVOT_SIMS_BACKEND` (files by default, or blob; Ax15)."""
    from .local import FilesSimStore

    backend = (os.getenv("PIVOT_SIMS_BACKEND") or "files").strip().lower()
    if backend == "blob":
        from .azure.blob import BlobSimStore

        return BlobSimStore.from_env()
    if backend == "files":
        return FilesSimStore()
    raise ValueError(f"unknown PIVOT_SIMS_BACKEND {backend!r}; expected files or blob")
