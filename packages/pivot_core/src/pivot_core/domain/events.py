"""Match events: the raw stream every other stage reads.

Modelled on real event feeds (StatsBomb, Opta, SPADL): continuous coordinates,
possession sequences, how each possession started, and whether the player was
under pressure. Player positions at the moment of an event come from the
tracking frame with the same `t` (see tracking.py).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, computed_field

from .common import ClockSeconds, Model, Point, Side, zone_of

EventType = Literal[
    "pass", "carry", "dribble", "shot", "save",
    "pressure", "duel", "tackle", "interception", "clearance", "block", "ball_recovery",
    "foul", "card", "offside", "substitution", "tactical_shift",
    "kickoff", "period_end",
]

ShotOutcome = Literal["goal", "saved", "off_target", "blocked", "post"]

# How the current possession started. "counter" = won in own half and attacked fast.
PlayPattern = Literal[
    "open_play", "counter", "corner", "free_kick", "throw_in", "goal_kick", "kick_off", "penalty",
]


class MatchEvent(Model):
    schema_version: Literal[1] = 1
    match_id: str
    seq: Annotated[int, Field(ge=0)]          # strictly increasing within a match
    event_id: str                             # "m063-s01042", shown in the UI as #1042
    t: ClockSeconds                           # also the timestamp of the matching tracking frame
    period: Literal[1, 2]
    type: EventType
    team: Side
    player_id: str | None = None
    receiver_id: str | None = None            # pass target; lets focus-player mode follow the ball
    location: Point | None = None
    end_location: Point | None = None         # passes, carries, shots
    outcome: Literal["success", "fail"] | None = None
    shot_outcome: ShotOutcome | None = None   # shots only; a goal is a shot with outcome "goal"
    xg: Annotated[float, Field(ge=0, le=1)] | None = None   # shots only
    ball_speed_kmh: Annotated[float, Field(ge=0, le=150)] | None = None   # passes and shots
    under_pressure: bool = False              # an opponent was within pressing distance
    possession_id: Annotated[int, Field(ge=0)] | None = None   # increases each time possession changes
    play_pattern: PlayPattern | None = None
    threat: float = 0.0                       # threat added by this event, from the threat grid
    meta: dict[str, str] = {}                 # card colour, players on and off, new formation, ...

    @computed_field
    @property
    def minute(self) -> int:
        """Match minute the event belongs to (0-based, so 62:30 is minute 62)."""
        return min(self.t // 60, 89)

    @computed_field
    @property
    def from_zone(self) -> tuple[int, int] | None:
        """Threat-grid zone of `location`."""
        return zone_of(self.location) if self.location else None

    @computed_field
    @property
    def to_zone(self) -> tuple[int, int] | None:
        """Threat-grid zone of `end_location`."""
        return zone_of(self.end_location) if self.end_location else None
