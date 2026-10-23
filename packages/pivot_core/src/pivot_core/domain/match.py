"""Teams, players and the match itself. All names are fictional."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import ClockSeconds, Model, Side

Position = Literal["GK", "DF", "MF", "FW"]
MatchStatus = Literal["scheduled", "live", "paused", "finished"]


class Player(Model):
    player_id: str                            # "h07" = home shirt 7, "a11" = away shirt 11
    name: str                                 # fictional, e.g. "R. Okafor"
    team: Side
    shirt_number: Annotated[int, Field(ge=1, le=99)]
    position: Position


class Team(Model):
    side: Side
    name: str                                 # fictional, e.g. "Harbour City"
    short_name: Annotated[str, Field(max_length=4)]   # "HBC", shown in the top bar
    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    players: list[Player]                     # starters first, then the bench


class Score(Model):
    home: Annotated[int, Field(ge=0)] = 0
    away: Annotated[int, Field(ge=0)] = 0


class Match(Model):
    match_id: str                             # "M-seed-20261021"
    seed: int
    preset: str | None = None                 # "demo-1021" for the recorded demo
    home: Team
    away: Team
    status: MatchStatus
    speed: Literal[1, 5, 20, 60] = 1          # replay speed multiplier
    clock: ClockSeconds = 0
    period: Literal[1, 2] = 1
    score: Score = Score()
