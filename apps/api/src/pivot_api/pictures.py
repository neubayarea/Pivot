"""Whole-match pictures (Bx12): data for the shot map, heatmaps, pass networks and average positions.

GET /api/matches/{id}/shots
GET /api/matches/{id}/heatmaps
GET /api/matches/{id}/pass-network[?min_passes=3]
GET /api/matches/{id}/positions
    each with [?up_to=<seconds>][&period=1|2|3|4]

Built by pivot_core.analytics.pictures from the stored events and tracking frames. Points are in
each team's attacking view (CONV-002): own goal at x = 0, the opponent's at x = 105. Read-only;
a finished match's answers are kept in memory after the first request.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict

from fastapi import APIRouter, HTTPException, Query, Request

from pivot_core.analytics import pictures
from pivot_core.domain import (
    AveragePositionsReport, HeatmapReport, Match, MatchEvent, PassNetworkReport, ShotMap, TrackingFrame,
)

from . import matchdata

router = APIRouter(prefix="/api")

KEEP = 64                                    # answers kept per app


async def _inputs(request: Request, match_id: str, up_to: int | None, period: int | None
                  ) -> tuple[Match, list[MatchEvent], list[TrackingFrame], int]:
    match = await request.app.state.adapters.matches.get_match(match_id)
    if match is None:
        raise HTTPException(404, f"match {match_id!r} not found")
    events, frames = await matchdata.inputs(request, match)
    last = matchdata.last_second(match, events, frames)
    cut = last if up_to is None else min(up_to, last)
    events = [e for e in events if e.t <= cut and (period is None or e.period == period)]
    frames = [f for f in frames if f.t <= cut and (period is None or f.period == period)]
    return match, events, frames, cut


async def _answer(request: Request, kind: str, match_id: str, up_to: int | None, period: int | None, build, *extra):
    """`build(match, events, frames, cut)` once per question for a finished match."""
    match, events, frames, cut = await _inputs(request, match_id, up_to, period)
    cache = matchdata.shared(request, "pictures", OrderedDict)
    key = (kind, match_id, cut, period, *extra)
    if match.status != "finished" or key not in cache:
        value = await asyncio.to_thread(build, match, events, frames, cut)
        if match.status != "finished":
            return value
        cache[key] = value
        while len(cache) > KEEP:
            cache.popitem(last=False)
    cache.move_to_end(key)
    return cache[key]


UpTo = Query(None, ge=0, description="elapsed seconds: only what happened by then")
PeriodQ = Query(None, ge=1, le=4, description="one period only: 1, 2, or extra time 3, 4")


@router.get("/matches/{match_id}/shots")
async def shot_map(request: Request, match_id: str, up_to: int | None = UpTo, period: int | None = PeriodQ) -> ShotMap:
    """Every shot, from the shooter's attacking view, with xG, outcome and the event id for the clip."""
    return await _answer(request, "shots", match_id, up_to, period, lambda m, e, f, cut: ShotMap(
        match_id=match_id, up_to_t=cut, period=period, shots=pictures.shots(e)))


@router.get("/matches/{match_id}/heatmaps")
async def heatmaps(request: Request, match_id: str, up_to: int | None = UpTo,
                   period: int | None = PeriodQ) -> HeatmapReport:
    """Where each team and each player spent their time, on a 21 x 14 grid (shares of the busiest cell)."""
    def build(m, e, f, cut):
        h = pictures.heatmaps(m, e, f)
        return HeatmapReport(match_id=match_id, up_to_t=cut, period=period, source=h["source"], cols=h["cols"],
                             rows=h["rows"], teams=h["teams"],
                             players=[{"player_id": pid, **v} for pid, v in h["players"].items()])
    return await _answer(request, "heat", match_id, up_to, period, build)


@router.get("/matches/{match_id}/pass-network")
async def pass_network(request: Request, match_id: str, up_to: int | None = UpTo, period: int | None = PeriodQ,
                       min_passes: int = Query(pictures.MIN_PASSES, ge=1, le=30)) -> PassNetworkReport:
    """Each side's starting eleven where they stood with the ball, and the completed passes between them."""
    return await _answer(request, "net", match_id, up_to, period, lambda m, e, f, cut: PassNetworkReport(
        match_id=match_id, up_to_t=cut, period=period, min_passes=min_passes,
        teams=pictures.pass_networks(m, e, f, min_passes)), min_passes)


@router.get("/matches/{match_id}/positions")
async def average_positions(request: Request, match_id: str, up_to: int | None = UpTo,
                            period: int | None = PeriodQ) -> AveragePositionsReport:
    """Everyone who played: mean position with their team on the ball and without it (needs frames)."""
    return await _answer(request, "pos", match_id, up_to, period, lambda m, e, f, cut: AveragePositionsReport(
        match_id=match_id, up_to_t=cut, period=period, players=pictures.average_positions(m, f)))
