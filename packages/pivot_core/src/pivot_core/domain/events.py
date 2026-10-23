"""Match events: the raw stream every other stage reads."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, computed_field

from .common import ClockSeconds, Model, Side, Zone

EventType = Literal[
    "pass", "carry", "shot", "goal", "tackle", "interception", "pressure",
    "foul", "card", "substitution", "kickoff", "period_end",
]


class MatchEvent(Model):
    schema_version: Literal[1] = 1
    match_id: str
    seq: Annotated[int, Field(ge=0)]          # strictly increasing within a match
    event_id: str                             # "m063-s01042", shown in the UI as #1042
    t: ClockSeconds
    period: Literal[1, 2]
    type: EventType
    team: Side
    player_id: str | None = None
    receiver_id: str | None = None            # pass target; lets focus-player mode follow the ball
    from_zone: Zone | None = None
    to_zone: Zone | None = None
    outcome: Literal["success", "fail"] | None = None
    xg: Annotated[float, Field(ge=0, le=1)] | None = None   # shots only
    threat: float = 0.0                       # threat added by this event, from the threat grid
    meta: dict[str, str] = {}                 # card colour, players on and off, ...

    @computed_field
    @property
    def minute(self) -> int:
        """Match minute the event belongs to (0-based, so 62:30 is minute 62)."""
        return min(self.t // 60, 89)
