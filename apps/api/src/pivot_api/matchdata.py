"""A stored match's events and tracking frames as models, and StatCalculators built from them.

Shared by the per-player numbers (players.py) and the team stats (team_stats.py). Reading and
checking 6,000 frames takes a second or two, so it happens once per match; a calculator cut at a
second of the match (`up_to`, for a replay or a live match) is kept for the last few seconds asked.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from pathlib import Path

from fastapi import Request

from pivot_core.analytics import StatCalculator
from pivot_core.domain import Match, MatchEvent, TrackingFrame

from . import sims

CUT_CACHE = 16                               # calculators cut at an up_to, per app


def frames_path(request: Request, match_id: str) -> Path | None:
    """The match's tracking frames: the recorded demo's file or a simulated match's cache file."""
    return getattr(request.app.state, "fixture_frames", {}).get(match_id) or \
        sims.frames_path(getattr(request.app.state, "sims_dir", sims.data_dir_from_env()), match_id)


def shared(request: Request, name: str, make):
    """An app-wide cache object, made on first use (app.py resets them at start-up)."""
    state = request.app.state
    if getattr(state, name, None) is None:
        setattr(state, name, make())
    return getattr(state, name)


async def inputs(request: Request, match: Match) -> tuple[list[MatchEvent], list[TrackingFrame]]:
    """Events and frames of a match, kept after the first read once the match is finished.
    No frames file: no frames."""
    cache = shared(request, "match_inputs", dict) if match.status == "finished" else {}
    async with shared(request, "match_inputs_lock", asyncio.Lock):
        if match.match_id not in cache:
            events = await request.app.state.adapters.matches.list_events(match.match_id)
            path = frames_path(request, match.match_id)
            frames = [] if path is None else await asyncio.to_thread(
                lambda: [TrackingFrame.model_validate(f) for f in sims.read_frames(path)])
            cache[match.match_id] = (events, frames)
        return cache[match.match_id]


async def calculator(request: Request, match: Match, up_to_t: int | None = None) -> StatCalculator:
    """The match's StatCalculator; with `up_to_t`, one that only sees the events and frames up to then."""
    events, frames = await inputs(request, match)
    if match.status != "finished":                     # still being played: nothing to keep
        keep = [e for e in events if up_to_t is None or e.t <= up_to_t]
        return await asyncio.to_thread(StatCalculator, match, keep,
                                       [f for f in frames if up_to_t is None or f.t <= up_to_t])
    full = shared(request, "match_calcs", dict)
    if up_to_t is None:
        if match.match_id not in full:
            full[match.match_id] = await asyncio.to_thread(StatCalculator, match, events, frames)
        return full[match.match_id]
    cut = shared(request, "match_calcs_cut", OrderedDict)
    key = (match.match_id, up_to_t)
    if key not in cut:
        cut[key] = await asyncio.to_thread(StatCalculator, match, [e for e in events if e.t <= up_to_t],
                                           [f for f in frames if f.t <= up_to_t])
        while len(cut) > CUT_CACHE:
            cut.popitem(last=False)
    cut.move_to_end(key)
    return cut[key]


def last_second(match: Match, events: list[MatchEvent], frames: list[TrackingFrame]) -> int:
    """The last elapsed second the match has data for."""
    return max([f.t for f in frames] + [e.t for e in events] + [p.end_t for p in match.periods], default=0)
