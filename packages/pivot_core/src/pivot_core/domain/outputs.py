"""Outputs for other systems: the broadcast overlay feed and the full-time recap."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import X, Y, ClockSeconds, Minute, Model, Period, Side
from .events import BodyPart, PlayPattern, ShotOutcome, ShotTechnique
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


# --- match pictures (Bx12): every point in the acting team's attacking view (CONV-002) ----------

class ShotMapShot(Model):
    """One shot: where from and where to, from the shooter's side, the goal they attack at x = 105."""

    event_id: str
    t: ClockSeconds
    period: Period
    clock_label: str                          # "38'", "45+2'"
    team: Side
    player_id: str | None = None
    x: X
    y: Y
    end_x: X | None = None
    end_y: Y | None = None
    xg: Annotated[float, Field(ge=0, le=1)] | None = None
    outcome: ShotOutcome | None = None
    body_part: BodyPart | None = None
    play_pattern: PlayPattern | None = None
    technique: ShotTechnique | None = None
    under_pressure: bool = False
    first_time: bool = False


class ShotMap(Model):
    """GET /api/matches/{id}/shots: every shot so far (the shootout left out)."""

    match_id: str
    up_to_t: ClockSeconds
    period: Period | None = None              # set when one period was asked for
    shots: list[ShotMapShot]


class HeatGrid(Model):
    samples: Annotated[int, Field(ge=0)]      # player-seconds (frames) or on-ball events counted
    cells: list[Annotated[float, Field(ge=0, le=1)]]   # row-major, a share of the busiest cell


class PlayerHeat(HeatGrid):
    player_id: str
    team: Side


class HeatmapReport(Model):
    """GET /api/matches/{id}/heatmaps: where each team and player spent their time."""

    match_id: str
    up_to_t: ClockSeconds
    period: Period | None = None
    source: Literal["frames", "events"]       # tracking frames (time spent) or on-ball events when there are none
    cols: Annotated[int, Field(ge=1)]         # along x, from the team's own goal
    rows: Annotated[int, Field(ge=1)]         # along y, from the team's right touchline
    teams: dict[Side, HeatGrid]
    players: list[PlayerHeat]


class PitchPoint(Model):
    x: X
    y: Y


class AveragePosition(Model):
    player_id: str
    team: Side
    seconds: Annotated[int, Field(ge=0)]      # on the pitch in the frames counted
    in_possession: PitchPoint | None = None   # mean position while their team had the ball
    out_of_possession: PitchPoint | None = None   # ... while the other team had it


class AveragePositionsReport(Model):
    """GET /api/matches/{id}/positions: everyone who played, from the tracking frames."""

    match_id: str
    up_to_t: ClockSeconds
    period: Period | None = None
    players: list[AveragePosition]


class PassNetworkNode(Model):
    player_id: str
    x: X                                      # mean position while their team had the ball
    y: Y
    passes: Annotated[int, Field(ge=0)]       # completed passes made
    received: Annotated[int, Field(ge=0)]     # completed passes received


class PassNetworkEdge(Model):
    from_id: str
    to_id: str
    passes: Annotated[int, Field(ge=1)]       # completed passes from one to the other


class TeamPassNetwork(Model):
    source: Literal["frames", "events"]       # where the node positions come from
    nodes: list[PassNetworkNode]              # the starting eleven
    edges: list[PassNetworkEdge]              # most passes first


class PassNetworkReport(Model):
    """GET /api/matches/{id}/pass-network: each side's starting eleven and who passed to whom."""

    match_id: str
    up_to_t: ClockSeconds
    period: Period | None = None
    min_passes: Annotated[int, Field(ge=1)]
    teams: dict[Side, TeamPassNetwork]


class PlayerPivotLink(Model):
    """A turning point a player took part in."""

    pivot_id: str
    minute: Minute
    in_trigger: bool                          # one of the events that set the pivot off is theirs
    event_ids: list[str]                      # their events from 5 minutes before to 5 after the pivot


class PlayerReport(Model):
    """What the page can show about one player, up to a point in the match (focus-player card)."""

    player_id: str
    name: str
    team: Side
    shirt_number: Annotated[int, Field(ge=1, le=99)]
    role: str                                 # detailed role, e.g. "CB"
    stats: PlayerMatchStats | None = None     # None: has not been on the pitch by up_to_t
    event_ids: list[str] = []                 # events they took part in, in order
    pivots: list[PlayerPivotLink] = []


class PlayerStatsReport(Model):
    """GET /api/matches/{id}/players/stats: every player of both squads, or the one asked for."""

    match_id: str
    up_to_t: ClockSeconds                     # elapsed seconds the numbers cover
    source: Literal["stored", "computed"]     # the numbers saved with the match, or worked out for up_to_t
    players: list[PlayerReport]


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
