"""Positions of every player and the ball, one frame per second of match time.

The simulator advances in one-second steps, so every frame is a real simulation
state, not an interpolation. The frontend may interpolate between frames for
smoother animation. Coordinates follow common.Point (metres, home attacks to x = 105).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import ClockSeconds, Model, Side, X, Y

FRAME_RATE_HZ = 1


class PlayerPosition(Model):
    player_id: str
    x: X
    y: Y
    speed_ms: Annotated[float, Field(ge=0, le=12)] = 0.0   # metres per second over the last step
    fitness: Annotated[float, Field(ge=0, le=1)] = 1.0     # 1 = fresh; drops over the match, resets for subs


class BallPosition(Model):
    x: X
    y: Y
    z: Annotated[float, Field(ge=0, le=30)] = 0.0          # height in metres
    owner_id: str | None = None               # player in control, None while the ball travels


class TrackingFrame(Model):
    match_id: str
    t: ClockSeconds
    period: Literal[1, 2]
    possession: Side | None                   # team in possession, None for a loose ball
    ball: BallPosition
    players: Annotated[list[PlayerPosition], Field(max_length=22)]   # players on the pitch only
