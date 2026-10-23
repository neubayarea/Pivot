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

# Zone on the 12 x 8 pitch grid: (column 0-11 towards the away goal, row 0-7).
Zone = tuple[Annotated[int, Field(ge=0, le=11)], Annotated[int, Field(ge=0, le=7)]]


class Model(BaseModel):
    """Base for every shared model: unknown fields are rejected so drift shows up early.

    Fields with defaults are always present in serialized output, so the exported
    schema marks them required and the frontend types do not make them optional.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, json_schema_serialization_defaults_required=True
    )
