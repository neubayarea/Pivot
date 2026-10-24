"""Composition root: pick the adapter set for the deployment profile (ADR-0001).

`PIVOT_PROFILE` is `local` (default), `c1` or `c2`. Only `local` exists so far; the Azure
adapters for c1/c2 come with A08.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from pivot_core.ports import LiveNegotiator, LivePublisher, MatchRepository, TraceRepository, WorkQueue

PROFILES = ("local", "c1", "c2")


@dataclass(frozen=True)
class Adapters:
    profile: str
    queue: WorkQueue
    matches: MatchRepository
    traces: TraceRepository
    live: LivePublisher
    negotiator: LiveNegotiator


def build_adapters(profile: str | None = None) -> Adapters:
    profile = (profile or os.getenv("PIVOT_PROFILE") or "local").strip().lower()
    if profile == "local":
        from .local import (
            InMemoryLivePublisher,
            InMemoryMatchRepository,
            InMemoryTraceRepository,
            InMemoryWorkQueue,
            LocalNegotiator,
        )

        return Adapters(
            profile=profile,
            queue=InMemoryWorkQueue(),
            matches=InMemoryMatchRepository(),
            traces=InMemoryTraceRepository(),
            live=InMemoryLivePublisher(),
            negotiator=LocalNegotiator(),
        )
    if profile in PROFILES:
        raise NotImplementedError(f"PIVOT_PROFILE={profile!r}: Azure adapters are not implemented yet (A08)")
    raise ValueError(f"unknown PIVOT_PROFILE {profile!r}; expected one of {', '.join(PROFILES)}")
