"""Outputs for other systems: the broadcast overlay feed and the full-time recap."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import ClockSeconds, Model, Side
from .match import Score
from .narrative import Language, Narrative


class OverlayItem(Model):
    """One graphic that a broadcast renderer can place on top of the live feed."""

    overlay_id: str
    kind: Literal["pivot", "goal", "card", "substitution"]
    ref_id: str                               # pivot_id or event_id it was built from
    show_at: ClockSeconds                     # match clock, so it syncs with the video
    hide_at: ClockSeconds
    team: Side
    player_id: str | None = None
    headline: Annotated[str, Field(max_length=60)]
    subline: Annotated[str, Field(max_length=90)] | None = None
    severity: Literal[1, 2, 3] | None = None  # pivots only


class OverlayFeed(Model):
    match_id: str
    language: Language
    up_to_seq: Annotated[int, Field(ge=0)]    # last event included, for incremental polling
    items: list[OverlayItem]


class Recap(Model):
    match_id: str
    final_score: Score
    pivot_ids: list[str]                      # pivots the recap is built from, in order
    narrative: Narrative
