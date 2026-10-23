"""Small shared types used across the domain models."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Side = Literal["home", "away"]

# Match clock in seconds from kick-off. Regulation time only: 0 to 5400.
ClockSeconds = Annotated[int, Field(ge=0, le=5400)]
Minute = Annotated[int, Field(ge=0, le=90)]

# Left-closed, right-open minute range, e.g. (55, 63) covers minutes 55 to 62.
MinuteWindow = tuple[Minute, Minute]

# Pitch coordinates in metres on a 105 x 68 pitch (the SPADL convention).
# Origin is the bottom-left corner seen from the main stand; the home team always
# attacks towards x = 105 and the away team towards x = 0, in both halves.
PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
X = Annotated[float, Field(ge=0, le=PITCH_LENGTH)]
Y = Annotated[float, Field(ge=0, le=PITCH_WIDTH)]
Point = tuple[X, Y]

# Threat grid: 16 x 12 cells of about 6.6 x 5.7 m, the resolution commonly used for
# expected-threat (xT) models. Zone = (column 0-15 towards the away goal, row 0-11).
GRID_COLS = 16
GRID_ROWS = 12
Zone = tuple[Annotated[int, Field(ge=0, le=GRID_COLS - 1)], Annotated[int, Field(ge=0, le=GRID_ROWS - 1)]]

# Tactical areas, always from the attacking team's point of view.
Third = Literal["defensive", "middle", "final"]
Lane = Literal["left_wing", "left_half_space", "centre", "right_half_space", "right_wing"]
Area = Literal["own_six_yard_box", "own_box", "opp_box", "opp_six_yard_box", "open"]

# Lane edges follow the lines of the penalty box (40.32 m wide) and six-yard box (18.32 m wide).
_LANE_EDGES = (13.84, 24.84, 43.16, 54.16)
_BOX_DEPTH, _SIX_DEPTH = 16.5, 5.5


def zone_of(p: tuple[float, float]) -> tuple[int, int]:
    """Map a pitch point to its threat-grid zone."""
    col = min(int(p[0] / PITCH_LENGTH * GRID_COLS), GRID_COLS - 1)
    row = min(int(p[1] / PITCH_WIDTH * GRID_ROWS), GRID_ROWS - 1)
    return (col, row)


def attacking_view(p: tuple[float, float], side: str) -> tuple[float, float]:
    """Point as seen by `side` attacking left to right: x from own goal, y from own right touchline."""
    x, y = p
    return (x, y) if side == "home" else (PITCH_LENGTH - x, PITCH_WIDTH - y)


def third_of(p: tuple[float, float], side: str) -> str:
    x, _ = attacking_view(p, side)
    return "defensive" if x < PITCH_LENGTH / 3 else "middle" if x < 2 * PITCH_LENGTH / 3 else "final"


def lane_of(p: tuple[float, float], side: str) -> str:
    # Facing the opponent's goal, the attacker's left is the high-y side.
    _, y = attacking_view(p, side)
    lanes = ("right_wing", "right_half_space", "centre", "left_half_space", "left_wing")
    return lanes[sum(y >= edge for edge in _LANE_EDGES)]


def area_of(p: tuple[float, float], side: str) -> str:
    x, y = attacking_view(p, side)
    in_box_width = _LANE_EDGES[0] <= y <= _LANE_EDGES[3]
    in_six_width = _LANE_EDGES[1] <= y <= _LANE_EDGES[2]
    if x >= PITCH_LENGTH - _SIX_DEPTH and in_six_width:
        return "opp_six_yard_box"
    if x >= PITCH_LENGTH - _BOX_DEPTH and in_box_width:
        return "opp_box"
    if x <= _SIX_DEPTH and in_six_width:
        return "own_six_yard_box"
    if x <= _BOX_DEPTH and in_box_width:
        return "own_box"
    return "open"


class Model(BaseModel):
    """Base for every shared model: unknown fields are rejected so drift shows up early.

    Fields with defaults are always present in serialized output, so the exported
    schema marks them required and the frontend types do not make them optional.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, json_schema_serialization_defaults_required=True
    )
