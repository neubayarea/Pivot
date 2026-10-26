"""Per-player numbers for a match (Bx9): what the focus-player card shows, no AI involved.

GET /api/matches/{id}/players/stats[?up_to=<seconds>][&player=<id>]

- The numbers are the player lines of RAT-001 and the stat vocabulary (`player_match_stats`, B10).
- For the whole match the API serves the lines saved with the match: the recorded demo's
  `player_stats` and those in a simulated match's cache file. For `up_to` before the final
  whistle they are worked out again from the stored events and frames, so a card can follow
  the replay clock.
- Each player also gets the events they took part in and the pivots they were part of: one of
  the events that set the pivot off, or any of theirs from 5 minutes before to 5 after it.

Only matches with tracking frames (the recorded demo and simulated matches) have player numbers:
minutes played, distance and speed come from the frames. Read-only: nothing is stored.
"""

from __future__ import annotations

import asyncio
import gzip
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from pivot_core.analytics import StatCalculator, player_match_stats
from pivot_core.domain import (
    Match, MatchEvent, Pivot, PlayerMatchStats, PlayerPivotLink, PlayerReport, PlayerStatsReport, TrackingFrame,
)

from . import sims

router = APIRouter(prefix="/api")

PIVOT_REACH_S = 5 * 60                       # a player's events this close to a pivot's minute count as part of it


def involved(e: MatchEvent) -> set[str]:
    """Who took part in an event: the player on it, the receiver, both sides of a substitution."""
    ids = {e.player_id, e.receiver_id}
    if e.substitution:
        ids |= {e.substitution.player_off_id, e.substitution.player_on_id}
    return {i for i in ids if i}


def _frames_path(request: Request, match_id: str) -> Path | None:
    return getattr(request.app.state, "fixture_frames", {}).get(match_id) or \
        sims.frames_path(getattr(request.app.state, "sims_dir", sims.data_dir_from_env()), match_id)


def _cache(request: Request, name: str) -> dict:
    state = request.app.state
    if getattr(state, name, None) is None:
        setattr(state, name, {})
    return getattr(state, name)


def _stored_lines(request: Request, match_id: str) -> list[dict] | None:
    """The player lines saved with the match: the recorded demo's file or the simulated match's cache file."""
    cache = _cache(request, "player_lines")
    if match_id in cache:
        return cache[match_id]
    lines = None
    fixture = getattr(request.app.state, "fixture_files", {}).get(match_id)
    if fixture is not None:
        lines = json.loads(fixture.read_text(encoding="utf-8")).get("player_stats")
    else:
        path = getattr(request.app.state, "sims_dir", sims.data_dir_from_env()) / f"{match_id}.{sims.SIM_VERSION}.json.gz"
        if sims.MATCH_ID.fullmatch(match_id) and path.is_file():
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                lines = json.load(fh).get("player_stats")
    cache[match_id] = lines
    return lines


async def _calculator(request: Request, match: Match, frames: Path) -> StatCalculator:
    """One StatCalculator per match, built on first use: reading 6,000 frames takes a second or two."""
    state = request.app.state
    cache = _cache(request, "player_calcs")
    if getattr(state, "player_calcs_lock", None) is None:
        state.player_calcs_lock = asyncio.Lock()
    async with state.player_calcs_lock:
        if match.match_id not in cache:
            events = await state.adapters.matches.list_events(match.match_id)

            def build() -> StatCalculator:
                rows = [TrackingFrame.model_validate(f) for f in sims.read_frames(frames)]
                return StatCalculator(match, events, rows)

            cache[match.match_id] = await asyncio.to_thread(build)
        return cache[match.match_id]


def _pivot_links(mine: list[MatchEvent], pivots: list[Pivot]) -> list[PlayerPivotLink]:
    out = []
    for p in pivots:
        near = [e.event_id for e in mine if abs(e.t - p.minute * 60) <= PIVOT_REACH_S]
        trigger = any(e.event_id in p.trigger_event_ids for e in mine)
        if near or trigger:
            out.append(PlayerPivotLink(pivot_id=p.pivot_id, minute=p.minute, in_trigger=trigger, event_ids=near))
    return out


@router.get("/matches/{match_id}/players/stats")
async def player_stats(request: Request, match_id: str, up_to: int | None = Query(None, ge=0),
                       player: str | None = None) -> PlayerStatsReport:
    """Every player of both squads (or `player` only), with their numbers up to `up_to` elapsed
    seconds (default: the whole match), the events they took part in and the pivots they were part of.

    404 for an unknown match or one without tracking frames; 422 for a player not in this match.
    """
    match = await request.app.state.adapters.matches.get_match(match_id)
    if match is None:
        raise HTTPException(404, f"match {match_id!r} not found")
    squad = [p for t in (match.home, match.away) for p in t.squad]
    if player is not None and player not in {p.player_id for p in squad}:
        raise HTTPException(422, f"player {player!r} is not in this match")
    frames = _frames_path(request, match_id)
    if frames is None:
        raise HTTPException(404, f"match {match_id!r} has no tracking frames, so no player numbers")

    calc = await _calculator(request, match, frames)
    end_t = int(calc._frames.t.max()) if len(calc._frames.t) else 0
    stored = _stored_lines(request, match_id) if up_to is None or up_to >= end_t else None
    if stored is not None:
        lines = [PlayerMatchStats.model_validate(s) for s in stored]
        source, cut = "stored", lines[0].up_to_t if lines else end_t
    else:
        cut = end_t if up_to is None else min(up_to, end_t)
        lines = await asyncio.to_thread(player_match_stats, calc, cut)
        source = "computed"
    by_player = {s.player_id: s for s in lines}

    events = [e for e in calc.events if e.t <= cut]
    pivots = [p for p in await request.app.state.adapters.matches.list_pivots(match_id)
              if p.status != "rejected" and p.minute * 60 <= cut]
    reports = []
    for p in squad:
        if player is not None and p.player_id != player:
            continue
        mine = [e for e in events if p.player_id in involved(e)]
        reports.append(PlayerReport(player_id=p.player_id, name=p.name, team=p.team, shirt_number=p.shirt_number,
                                    role=p.role, stats=by_player.get(p.player_id),
                                    event_ids=[e.event_id for e in mine],
                                    pivots=_pivot_links(mine, pivots)))
    return PlayerStatsReport(match_id=match_id, up_to_t=cut, source=source, players=reports)
