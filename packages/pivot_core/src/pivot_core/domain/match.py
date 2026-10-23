"""Teams and the match itself. All names are fictional."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import ClockSeconds, Model, Side
from .context import MatchContext
from .lineup import TeamSheet, TeamTactics
from .people import Coach, Player

MatchStatus = Literal["scheduled", "live", "paused", "finished"]


class Team(Model):
    side: Side
    club_id: str                              # matches CareerStint.club_id, so reunions can be found
    name: str                                 # fictional, e.g. "Harbour City"
    short_name: Annotated[str, Field(max_length=4)]   # "HBC", shown in the top bar
    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    coach: Coach
    squad: list[Player]                       # everyone available for this match
    sheet: TeamSheet                          # starting team sheet; changes arrive as events
    tactics: TeamTactics                      # starting tactics; changes arrive as events


class Score(Model):
    home: Annotated[int, Field(ge=0)] = 0
    away: Annotated[int, Field(ge=0)] = 0


class Match(Model):
    match_id: str                             # "M-seed-20261021"
    seed: int
    preset: str | None = None                 # "demo-1021" for the recorded demo
    home: Team
    away: Team
    context: MatchContext
    status: MatchStatus
    speed: Literal[1, 5, 20, 60] = 1          # replay speed multiplier
    clock: ClockSeconds = 0
    period: Literal[1, 2] = 1
    score: Score = Score()
