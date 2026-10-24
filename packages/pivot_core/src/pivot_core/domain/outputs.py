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
    kind: Literal["pivot", "goal", "card", "substitution", "var_review", "injury", "player_rating"]
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


class PlayerMatchStats(Model):
    """One player's line for this match, updated live, like the ratings in score apps."""

    match_id: str
    player_id: str
    up_to_t: ClockSeconds                     # stats include everything up to this elapsed time
    minutes_played: Annotated[int, Field(ge=0, le=180)]
    rating: Annotated[float, Field(ge=1, le=10)]   # 6.0 is an average display; formula in the data definitions
    goals: Annotated[int, Field(ge=0)] = 0
    assists: Annotated[int, Field(ge=0)] = 0
    shots: Annotated[int, Field(ge=0)] = 0
    xg: Annotated[float, Field(ge=0)] = 0.0
    xa: Annotated[float, Field(ge=0)] = 0.0
    passes: Annotated[int, Field(ge=0)] = 0
    pass_accuracy_pct: Annotated[float, Field(ge=0, le=100)] | None = None
    key_passes: Annotated[int, Field(ge=0)] = 0
    progressive_passes: Annotated[int, Field(ge=0)] = 0
    dribbles_won: Annotated[int, Field(ge=0)] = 0
    tackles_won: Annotated[int, Field(ge=0)] = 0
    interceptions: Annotated[int, Field(ge=0)] = 0
    duels_won: Annotated[int, Field(ge=0)] = 0
    aerials_won: Annotated[int, Field(ge=0)] = 0
    fouls_committed: Annotated[int, Field(ge=0)] = 0
    saves: Annotated[int, Field(ge=0)] = 0          # keepers
    distance_km: Annotated[float, Field(ge=0, le=20)] = 0.0
    top_speed_kmh: Annotated[float, Field(ge=0, le=45)] = 0.0
    sprints: Annotated[int, Field(ge=0)] = 0


class Recap(Model):
    match_id: str
    final_score: Score
    pivot_ids: list[str]                      # pivots the recap is built from, in order
    narrative: Narrative
