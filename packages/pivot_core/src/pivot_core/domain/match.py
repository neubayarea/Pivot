"""Teams, players and the match itself. All names are fictional."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, computed_field

from .common import ClockSeconds, Model, Side

Position = Literal["GK", "DF", "MF", "FW"]

# Detailed role, close to what event providers use. It sets the player's anchor
# point in the formation and which actions they tend to choose.
Role = Literal[
    "GK",
    "LB", "CB", "RB", "LWB", "RWB",
    "DM", "CM", "AM", "LM", "RM",
    "LW", "RW", "ST",
]

ROLE_POSITION: dict[str, Position] = {
    "GK": "GK",
    "LB": "DF", "CB": "DF", "RB": "DF", "LWB": "DF", "RWB": "DF",
    "DM": "MF", "CM": "MF", "AM": "MF", "LM": "MF", "RM": "MF",
    "LW": "FW", "RW": "FW", "ST": "FW",
}

MatchStatus = Literal["scheduled", "live", "paused", "finished"]

Rating = Annotated[int, Field(ge=1, le=99)]


class PlayerAttributes(Model):
    """Ability ratings the simulator uses, so players differ from one another."""

    pace: Rating                              # top speed and acceleration
    passing: Rating                           # pass success and range
    dribbling: Rating                         # carrying and beating a man
    shooting: Rating                          # shot accuracy and power
    defending: Rating                         # tackles, interceptions, positioning
    physical: Rating                          # duels and aerial balls
    stamina: Rating                           # how fast fitness drops over the match
    goalkeeping: Rating = 10                  # only meaningful for keepers


class Player(Model):
    player_id: str                            # "h07" = home shirt 7, "a11" = away shirt 11
    name: str                                 # fictional, e.g. "R. Okafor"
    team: Side
    shirt_number: Annotated[int, Field(ge=1, le=99)]
    role: Role
    preferred_foot: Literal["left", "right", "both"] = "right"
    attributes: PlayerAttributes

    @computed_field
    @property
    def position(self) -> Position:
        """Broad position group derived from `role`."""
        return ROLE_POSITION[self.role]


class Team(Model):
    side: Side
    name: str                                 # fictional, e.g. "Harbour City"
    short_name: Annotated[str, Field(max_length=4)]   # "HBC", shown in the top bar
    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    formation: Annotated[str, Field(pattern=r"^\d(-\d){2,4}$")]   # starting shape, e.g. "4-3-3"
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
