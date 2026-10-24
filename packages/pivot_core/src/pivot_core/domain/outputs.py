"""Outputs for other systems: the broadcast overlay feed and the full-time recap."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import ClockSeconds, Minute, Model, Period, Side
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


OVERLAY_CARD_SECONDS = 12                     # how long a pivot card stays on screen


class OverlayCard(Model):
    """A confirmed pivot as a lower-third card, timed on the match clock (FR-26)."""

    pivot_id: str
    minute: Minute
    minute_label: str                         # "63'" or "45+2'", shown in the red box
    show_at: ClockSeconds                     # card is on screen for show_at <= clock < hide_at
    hide_at: ClockSeconds
    direction: Side                           # side the momentum swung towards
    direction_team: str                       # that team's name, "Momentum -> Northgate Rovers"
    severity: Literal[1, 2, 3]
    status: Literal["confirmed", "degraded"]  # only checked pivots go on air
    headline: str
    subline: str | None = None                # first sentence of the explanation


class OverlayScoreboard(Model):
    home_short: str
    away_short: str
    score: Score
    period: Period
    clock_label: str


class OverlayFrame(Model):
    """What the overlay shows at one moment of the match clock: the score bug and at most one card."""

    match_id: str
    clock: ClockSeconds
    scoreboard: OverlayScoreboard
    card: OverlayCard | None = None


class OverlayTimeline(Model):
    """Every card of a match in clock order, never overlapping, for recordings and the preview page."""

    match_id: str
    card_seconds: int = OVERLAY_CARD_SECONDS
    cards: list[OverlayCard]


class Recap(Model):
    match_id: str
    final_score: Score
    pivot_ids: list[str]                      # pivots the recap is built from, in order
    narrative: Narrative
