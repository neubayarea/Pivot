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

# Zone on the 12 x 8 grid used by the threat model: (column 0-11 towards the away goal, row 0-7).
Zone = tuple[Annotated[int, Field(ge=0, le=11)], Annotated[int, Field(ge=0, le=7)]]


def zone_of(p: tuple[float, float]) -> tuple[int, int]:
    """Map a pitch point to its threat-grid zone."""
    col = min(int(p[0] / PITCH_LENGTH * 12), 11)
    row = min(int(p[1] / PITCH_WIDTH * 8), 7)
    return (col, row)


class Model(BaseModel):
    """Base for every shared model: unknown fields are rejected so drift shows up early.

    Fields with defaults are always present in serialized output, so the exported
    schema marks them required and the frontend types do not make them optional.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, json_schema_serialization_defaults_required=True
    )
