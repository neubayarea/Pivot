"""Small shared types used across the domain models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Side = Literal["home", "away"]

# Time. `t` is elapsed match time in seconds since the first kick-off, counting stoppage
# time and extra time, so it only ever goes up and is unique across the match (the half-time
# break is not counted). A "minute" in the data is t // 60 on that same elapsed clock; what
# a broadcast shows ("45+2'") is derived from the period and the time into it, see clock_label.
#
# Periods follow the StatsBomb numbering: 1 and 2 are the halves, 3 and 4 extra time,
# 5 the penalty shootout.
Period = Literal[1, 2, 3, 4, 5]
PERIOD_BASE_MINUTE = {1: 0, 2: 45, 3: 90, 4: 105}
PERIOD_LENGTH_MINUTES = {1: 45, 2: 45, 3: 15, 4: 15}

ClockSeconds = Annotated[int, Field(ge=0, le=3 * 3600)]   # generous upper bound incl. a shootout
PeriodSeconds = Annotated[int, Field(ge=0, le=3600)]
Minute = Annotated[int, Field(ge=0, le=180)]

# Left-closed, right-open range of elapsed minutes, e.g. (55, 63) covers minutes 55 to 62.
MinuteWindow = tuple[Minute, Minute]


def clock_label(period: int, period_t: int) -> str:
    """Broadcast-style clock: 63' in normal time, 45+2' in stoppage time, PEN in a shootout."""
    if period == 5:
        return "PEN"
    base, length = PERIOD_BASE_MINUTE[period], PERIOD_LENGTH_MINUTES[period]
    m = period_t // 60
    if m < length:
        return f"{base + m + 1}'"
    return f"{base + length}+{m - length + 1}'"


def label_at(period_starts: Mapping[int, int], t: int) -> str:
    """clock_label for elapsed second `t`, from when each period started on the elapsed clock
    (period -> start_t: Match.periods, or period_starts of the events). This is how every elapsed
    minute in the data is shown to people: a pivot at minute m reads label_at(starts, m * 60)."""
    started = [(start, period) for period, start in period_starts.items() if start <= t]
    if not started:
        return clock_label(1, t)
    start, period = max(started)
    return clock_label(period, t - start)

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
