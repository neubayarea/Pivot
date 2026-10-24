"""REST endpoints the web app reads (architecture §7.1, FR-17). Everything comes from the storage ports."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pivot_adapters import Adapters
from pivot_core.domain import Match, MatchEvent, MinuteMetric, Pivot

router = APIRouter(prefix="/api")


class NegotiateResponse(BaseModel):
    url: str                                  # WebSocket URL the browser connects to


def _adapters(request: Request) -> Adapters:
    return request.app.state.adapters


async def _match_or_404(request: Request, match_id: str) -> Match:
    match = await _adapters(request).matches.get_match(match_id)
    if match is None:
        raise HTTPException(404, f"match {match_id!r} not found")
    return match


@router.get("/matches")
async def list_matches(request: Request) -> list[Match]:
    """Stored matches, most recent first."""
    return await _adapters(request).matches.list_matches()


@router.get("/matches/{match_id}")
async def get_match(request: Request, match_id: str) -> Match:
    """Score, clock, status, teams and line-ups."""
    return await _match_or_404(request, match_id)


@router.get("/matches/{match_id}/timeline")
async def get_timeline(request: Request, match_id: str) -> list[MinuteMetric]:
    """Per-minute momentum and threat, in minute order (the S1 curve)."""
    await _match_or_404(request, match_id)
    return await _adapters(request).matches.list_metrics(match_id)


@router.get("/matches/{match_id}/events")
async def list_events(request: Request, match_id: str, since: int = -1) -> list[MatchEvent]:
    """Events with seq > `since`, in seq order; pass the last seq seen to catch up after a reconnect."""
    await _match_or_404(request, match_id)
    return await _adapters(request).matches.list_events(match_id, since_seq=since)


@router.get("/matches/{match_id}/pivots")
async def list_pivots(request: Request, match_id: str) -> list[Pivot]:
    """Pivots of a match in minute order, pending ones included."""
    await _match_or_404(request, match_id)
    return await _adapters(request).matches.list_pivots(match_id)


@router.get("/pivots/{pivot_id}")
async def get_pivot(request: Request, pivot_id: str) -> Pivot:
    """One pivot by id ("{match_id}:p{minute}")."""
    match_id, sep, _ = pivot_id.rpartition(":p")
    pivot = await _adapters(request).matches.get_pivot(match_id, pivot_id) if sep else None
    if pivot is None:
        raise HTTPException(404, f"pivot {pivot_id!r} not found")
    return pivot


@router.post("/negotiate")
async def negotiate(request: Request, match_id: str | None = None) -> NegotiateResponse:
    """Where the browser opens its realtime connection: the local WebSocket, or Web PubSub in the cloud."""
    return NegotiateResponse(url=await _adapters(request).negotiator.negotiate(match_id))
