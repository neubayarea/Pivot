"""Match events: the raw stream every other stage reads.

Modelled on real event feeds (StatsBomb, Opta, SPADL): continuous coordinates,
possession sequences, how each possession started, and whether the player was
under pressure. Player positions at the moment of an event come from the
tracking frame with the same `t` (see tracking.py).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, computed_field

from .common import (
    Area, ClockSeconds, Lane, Model, Period, PeriodSeconds, Point, Side, Third, area_of,
    clock_label, lane_of, third_of, zone_of,
)
from .lineup import Substitution, TeamSheet, TeamTactics
from .officials import FoulDetail, InjuryInfo, VarReview

EventType = Literal[
    "pass", "carry", "dribble", "shot", "goalkeeper",
    "pressure", "duel", "tackle", "interception", "clearance", "block", "ball_recovery",
    "foul", "card", "offside", "var_review", "injury", "substitution", "tactical_shift",
    "kickoff", "added_time", "period_end",
]

# "disallowed": the ball went in but VAR ruled the goal out (EVT-016); not a goal, not on target.
ShotOutcome = Literal["goal", "saved", "off_target", "blocked", "post", "disallowed"]

# How the current possession started. "counter" = won in own half and attacked fast.
PlayPattern = Literal[
    "open_play", "counter", "corner", "free_kick", "throw_in", "goal_kick", "kick_off", "penalty",
]

PassType = Literal[
    "regular", "cross", "through_ball", "switch", "cutback", "long_ball", "back_pass",
    "corner", "free_kick", "throw_in", "goal_kick", "kick_off", "keeper_throw", "keeper_kick",
]
PassHeight = Literal["ground", "low", "high"]   # low = off the grass but below shoulder height
Delivery = Literal["inswing", "outswing", "straight"]   # crosses, corners and free kicks into the box
BodyPart = Literal["left_foot", "right_foot", "head", "other"]
DuelType = Literal["aerial", "ground"]
# StatsBomb shot techniques.
ShotTechnique = Literal[
    "normal", "volley", "half_volley", "lob", "backheel", "diving_header", "overhead_kick",
]
PassTechnique = Literal["normal", "chip", "flick_on", "lay_off", "backheel", "outside_foot"]

# What the keeper did in a "goalkeeper" event (modelled on StatsBomb's goalkeeper event types).
KeeperAction = Literal[
    "shot_saved", "shot_parried", "tipped_over", "goal_conceded", "claim", "punch",
    "sweep", "smother", "pick_up",
]
KeeperTechnique = Literal["standing", "diving", "reflex"]


class MatchEvent(Model):
    schema_version: Literal[1] = 1
    match_id: str
    seq: Annotated[int, Field(ge=0)]          # strictly increasing within a match
    event_id: str                             # "m063-s01042", shown in the UI as #1042
    t: ClockSeconds                           # elapsed time; also the key of the matching tracking frame
    period: Period
    period_t: PeriodSeconds                   # seconds since this period kicked off
    type: EventType
    team: Side
    player_id: str | None = None
    receiver_id: str | None = None            # pass target; lets focus-player mode follow the ball
    location: Point | None = None
    end_location: Point | None = None         # passes, carries, shots
    outcome: Literal["success", "fail"] | None = None
    # Probability the simulator gave this action of succeeding when it was attempted
    # (passes, dribbles, tackles, duels). Pass difficulty = 1 - success_prob.
    success_prob: Annotated[float, Field(ge=0, le=1)] | None = None
    shot_outcome: ShotOutcome | None = None   # shots only; a goal is a shot with outcome "goal"
    xg: Annotated[float, Field(ge=0, le=1)] | None = None   # shots only
    shot_end_height_m: Annotated[float, Field(ge=0, le=10)] | None = None   # height at the goal line; the goal is 2.44 m
    shot_technique: ShotTechnique | None = None   # shots only
    pass_technique: PassTechnique | None = None   # passes only
    first_time: bool = False                  # shot or pass struck without a controlling touch
    deflected: bool = False                   # pass or shot touched by another player on its way
    # Penalty shootout kicks are shots in period 5 with play_pattern "penalty"; this is the round (1-5, then sudden death).
    shootout_round: Annotated[int, Field(ge=1, le=30)] | None = None
    added_minutes: Annotated[int, Field(ge=0, le=20)] | None = None   # "added_time" events: minutes shown on the board
    keeper_location: Point | None = None      # shots: where the defending keeper stood at the moment of the shot
    keeper_action: KeeperAction | None = None   # "goalkeeper" events only
    keeper_technique: KeeperTechnique | None = None
    duel_type: DuelType | None = None         # duels only
    delivery: Delivery | None = None          # crosses and set-piece deliveries
    counterpress: bool = False                # defensive action within 5 s of this team losing the ball
    foul: FoulDetail | None = None            # "foul" and "card" events: type, advantage, card
    var: VarReview | None = None              # "var_review" events only
    injury: InjuryInfo | None = None          # "injury" events only
    pass_type: PassType | None = None         # passes only
    pass_height: PassHeight | None = None     # passes only
    body_part: BodyPart | None = None         # passes, shots, clearances
    ball_speed_kmh: Annotated[float, Field(ge=0, le=150)] | None = None   # passes and shots
    under_pressure: bool = False              # an opponent was within pressing distance
    possession_id: Annotated[int, Field(ge=0)] | None = None   # increases each time possession changes
    play_pattern: PlayPattern | None = None
    # Linked events: pass and the shot it set up, pressure and the action it hit,
    # foul and the card that followed, tackle and the duel it won.
    related_event_ids: list[str] = []
    threat: float = 0.0                       # threat added by this event, from the threat grid
    # Coach decisions. Kick-off events carry each team's starting sheet and tactics;
    # tactical shifts and substitutions carry the sheet and tactics that apply from now on.
    team_sheet: TeamSheet | None = None
    tactics: TeamTactics | None = None
    substitution: Substitution | None = None
    meta: dict[str, str] = {}                 # card colour and other small details

    @computed_field
    @property
    def minute(self) -> int:
        """Elapsed match minute (0-based, stoppage and extra time included): t // 60."""
        return self.t // 60

    @computed_field
    @property
    def clock_label(self) -> str:
        """What a broadcast would show: 63', 45+2', 105+1', or PEN in the shootout."""
        return clock_label(self.period, self.period_t)

    @computed_field
    @property
    def from_zone(self) -> tuple[int, int] | None:
        """Threat-grid zone of `location`."""
        return zone_of(self.location) if self.location else None

    @computed_field
    @property
    def to_zone(self) -> tuple[int, int] | None:
        """Threat-grid zone of `end_location`."""
        return zone_of(self.end_location) if self.end_location else None

    @computed_field
    @property
    def third(self) -> Third | None:
        """Pitch third of `location`, from the acting team's point of view."""
        return third_of(self.location, self.team) if self.location else None

    @computed_field
    @property
    def lane(self) -> Lane | None:
        """Vertical lane of `location` (wings, half-spaces, centre), from the acting team's view."""
        return lane_of(self.location, self.team) if self.location else None

    @computed_field
    @property
    def area(self) -> Area | None:
        """Penalty or six-yard box `location` falls in, if any, from the acting team's view."""
        return area_of(self.location, self.team) if self.location else None
