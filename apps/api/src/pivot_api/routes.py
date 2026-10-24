"""REST endpoints the web app reads (architecture §7.1, FR-17). Everything comes from the storage ports."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pivot_adapters import Adapters
from pivot_core.domain import (
    AgentTrace,
    Match,
    MatchEvent,
    MinuteMetric,
    OverlayFrame,
    OverlayTimeline,
    Pivot,
    ViewerPrefs,
)
from pivot_core.domain.common import Side
from pivot_core.domain.narrative import Audience, Language

from . import overlay
from .personalize import Personalizer

router = APIRouter(prefix="/api")


class NegotiateResponse(BaseModel):
    url: str                                  # WebSocket URL the browser connects to


class PersonalizedPivot(Pivot):
    """A pivot whose narrative is the version for the asked viewer prefs (A11)."""

    # What the narrative was actually written for. Differs from the query when that version could
    # not be written yet: then it is the default version (analyst, English).
    prefs: ViewerPrefs


def _adapters(request: Request) -> Adapters:
    return request.app.state.adapters


def _personalizer(request: Request) -> Personalizer:
    return request.app.state.personalizer


def _prefs(match: Match, lang: Language, audience: Audience, team: Side | None, player: str | None) -> ViewerPrefs:
    if player and player not in {p.player_id for t in (match.home, match.away) for p in t.squad}:
        raise HTTPException(422, f"player {player!r} is not in this match")
    return ViewerPrefs(audience=audience, language=lang, focus_team=team, focus_player_id=player or None)


async def _personalized(request: Request, pivot: Pivot, prefs: ViewerPrefs) -> PersonalizedPivot:
    result = await _personalizer(request).personalize(pivot, prefs)
    return PersonalizedPivot(**dict(result.pivot), prefs=result.prefs)


async def _match_or_404(request: Request, match_id: str) -> Match:
    match = await _adapters(request).matches.get_match(match_id)
    if match is None:
        raise HTTPException(404, f"match {match_id!r} not found")
    return match


@router.get("/matches")
async def list_matches(request: Request) -> list[Match]:
    """Stored matches, most recent first."""
    return await _adapters(request).matches.list_matches()


@router.get("/sims")
async def sims_status(request: Request) -> dict:
    """Progress of the simulated matches the local API builds at startup (Ax6): `generating` until all are stored."""
    status = getattr(request.app.state, "sims", None)
    return status.as_dict() if status else {"total": 0, "ready": 0, "failed": 0, "generating": False, "match_ids": []}


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
async def list_pivots(request: Request, match_id: str, lang: Language = "en", audience: Audience = "analyst",
                      team: Side | None = None, player: str | None = None) -> list[PersonalizedPivot]:
    """Pivots of a match in minute order, pending ones included, each written for the viewer prefs.

    `lang` en/zh/es, `audience` analyst/fan, `team` home/away and `player` (a player id) pick the
    version of each narrative (FR-23, FR-24, FR-25); `prefs` in each item says which one it is.
    """
    match = await _match_or_404(request, match_id)
    prefs = _prefs(match, lang, audience, team, player)
    pivots = await _adapters(request).matches.list_pivots(match_id)
    return list(await asyncio.gather(*(_personalized(request, p, prefs) for p in pivots)))


@router.get("/pivots/{pivot_id}")
async def get_pivot(request: Request, pivot_id: str, lang: Language = "en", audience: Audience = "analyst",
                    team: Side | None = None, player: str | None = None) -> PersonalizedPivot:
    """One pivot by id ("{match_id}:p{minute}"), written for the viewer prefs (same parameters as the list)."""
    match_id, sep, _ = pivot_id.rpartition(":p")
    repo = _adapters(request).matches
    pivot = await repo.get_pivot(match_id, pivot_id) if sep else None
    match = await repo.get_match(match_id) if pivot else None
    if pivot is None or match is None:
        raise HTTPException(404, f"pivot {pivot_id!r} not found")
    return await _personalized(request, pivot, _prefs(match, lang, audience, team, player))


@router.get("/matches/{match_id}/traces")
async def list_match_traces(request: Request, match_id: str) -> list[AgentTrace]:
    """Every agent step of the match (S4), grouped by `chain_id` and in `step` order within each chain.

    Candidates the judge turned down are here too: their chain has `input_ref` = the candidate id.
    """
    await _match_or_404(request, match_id)
    return await _adapters(request).traces.list_traces(match_id)


@router.get("/pivots/{pivot_id}/traces")
async def list_pivot_traces(request: Request, pivot_id: str) -> list[AgentTrace]:
    """Every chain that worked on this pivot ("{match_id}:p{minute}"), same order as the match list.

    Rewrites, template fallbacks and redeliveries all count; a candidate judged "not a pivot" has the
    same id, so it is found here even when no pivot was stored for it.
    """
    match_id, sep, _ = pivot_id.rpartition(":p")
    adapters = _adapters(request)
    traces = [t for t in await adapters.traces.list_traces(match_id) if t.input_ref == pivot_id] if sep else []
    if not traces and (not sep or await adapters.matches.get_pivot(match_id, pivot_id) is None):
        raise HTTPException(404, f"pivot {pivot_id!r} not found")
    return traces


async def _overlay_timeline(request: Request, match_id: str) -> tuple[Match, OverlayTimeline, list[MatchEvent]]:
    match = await _match_or_404(request, match_id)
    repo = _adapters(request).matches
    events = await repo.list_events(match_id)
    return match, overlay.build_timeline(match, await repo.list_pivots(match_id), events), events


@router.get("/matches/{match_id}/overlay")
async def get_overlay(request: Request, match_id: str, clock: str | None = None) -> OverlayFrame:
    """Score bug and the pivot card (if any) to show at `clock` ("63:20" or seconds); default is the live clock."""
    try:
        t = None if clock is None else overlay.parse_clock(clock)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    match, timeline, events = await _overlay_timeline(request, match_id)
    return overlay.frame_at(match, timeline, events, match.clock if t is None else t)


@router.get("/matches/{match_id}/overlay/timeline")
async def get_overlay_timeline(request: Request, match_id: str) -> OverlayTimeline:
    """Every overlay card of the match with its show and hide clock, for recordings and the preview page."""
    _, timeline, _ = await _overlay_timeline(request, match_id)
    return timeline


@router.post("/negotiate")
async def negotiate(request: Request, match_id: str | None = None) -> NegotiateResponse:
    """Where the browser opens its realtime connection: the local WebSocket, or Web PubSub in the cloud."""
    return NegotiateResponse(url=await _adapters(request).negotiator.negotiate(match_id))
