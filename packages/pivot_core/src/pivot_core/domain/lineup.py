"""The coach's team sheet: formation, who starts where, set-piece takers and tactics."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import Model, Point
from .people import Role

Formation = Annotated[str, Field(pattern=r"^\d(-\d){2,4}$")]   # "4-3-3", "4-2-3-1", "5-4-1"
Level = Literal["low", "mid", "high"]


class LineupSlot(Model):
    player_id: str
    slot: Annotated[int, Field(ge=1, le=11)]  # 1 = goalkeeper, then back to front, left to right
    role: Role
    # Base position in the formation, seen from the team's own goal (x = 0) towards the
    # opponent's goal (x = 105), y = 0 on the team's right touchline. The simulator mirrors it
    # for the away side and moves players around it every second.
    anchor: Point


class TeamSheet(Model):
    formation: Formation
    starters: Annotated[list[LineupSlot], Field(min_length=7, max_length=11)]   # fewer after red cards
    bench: Annotated[list[str], Field(max_length=15)] = []
    captain_id: str
    penalty_taker_id: str
    free_kick_taker_id: str
    corner_taker_left_id: str
    corner_taker_right_id: str


InstructionKind = Literal[
    "stay_back", "get_forward", "overlap", "underlap", "cut_inside", "stay_wide",
    "roam", "hold_position", "press_more", "sit_deeper", "man_mark",
]


class PlayerInstruction(Model):
    player_id: str
    instruction: InstructionKind
    target_player_id: str | None = None       # man_mark only


class SetPieceTactics(Model):
    corner_delivery: Literal["inswing", "outswing", "short", "mixed"] = "mixed"
    corner_target: Literal["near_post", "far_post", "penalty_spot", "edge_of_box", "mixed"] = "mixed"
    free_kick_style: Literal["direct", "cross", "short", "mixed"] = "mixed"
    players_forward_on_corners: Annotated[int, Field(ge=0, le=9)] = 5
    corner_defence: Literal["zonal", "man", "mixed"] = "mixed"
    players_back_on_corners: Annotated[int, Field(ge=0, le=3)] = 1   # left upfield for the counter


class TeamTactics(Model):
    line_height: Level = "mid"                # where the back line holds
    press: Level = "mid"                      # how aggressively the team hunts the ball
    width: Literal["narrow", "normal", "wide"] = "normal"
    tempo: Literal["slow", "normal", "fast"] = "normal"
    passing: Literal["short", "mixed", "direct"] = "mixed"
    attack_focus: Literal["left", "centre", "right", "balanced"] = "balanced"
    counter_attack: bool = False              # break quickly after winning the ball
    offside_trap: bool = False
    time_wasting: bool = False                # slow restarts when protecting a lead
    set_pieces: SetPieceTactics = SetPieceTactics()
    instructions: list[PlayerInstruction] = []


class Substitution(Model):
    player_off_id: str
    player_on_id: str
    slot: Annotated[int, Field(ge=1, le=11)]  # slot the new player takes in the team sheet
    reason: Literal["tactical", "fatigue", "injury", "card_risk", "time_wasting"]
