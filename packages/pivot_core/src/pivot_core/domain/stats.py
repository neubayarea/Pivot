"""Stat vocabulary and the references that tie every number the AI writes to a recomputable stat."""

from __future__ import annotations

from typing import Literal

from .common import MinuteWindow, Model, Side

# First version of the stat vocabulary: 15 event stats, 4 shape stats that come from
# the tracking frames, and 4 standard analytics metrics (23 in total). D02 owns the
# wording and B05 owns the calculation; both must match this list exactly.
StatMetric = Literal[
    "possession_pct",
    "passes",
    "pass_accuracy_pct",
    "passes_final_third",
    "box_entries",
    "shots",
    "shots_on_target",
    "xg",
    "threat_total",
    "pressures",
    "tackles_won",
    "interceptions",
    "duels_won",
    "turnovers",
    "momentum_avg",
    "line_height_m",          # mean distance of the back line from its own goal
    "team_width_m",           # mean spread of the outfield players across the pitch
    "press_distance_m",       # mean distance from the ball carrier to the nearest opponent
    "distance_covered_km",
    "progressive_passes",     # passes that move the ball clearly closer to goal (see the data definitions)
    "ppda",                   # opponent passes allowed per defensive action in their build-up zone
    "xa",                     # expected assists: xG of the shots a player's passes set up
    "field_tilt_pct",         # share of both teams' final-third touches
]

StatUnit = Literal["count", "pct", "xg", "index", "m", "km", "ratio"]

STAT_UNITS: dict[str, StatUnit] = {
    "possession_pct": "pct",
    "passes": "count",
    "pass_accuracy_pct": "pct",
    "passes_final_third": "count",
    "box_entries": "count",
    "shots": "count",
    "shots_on_target": "count",
    "xg": "xg",
    "threat_total": "index",
    "pressures": "count",
    "tackles_won": "count",
    "interceptions": "count",
    "duels_won": "count",
    "turnovers": "count",
    "momentum_avg": "index",
    "line_height_m": "m",
    "team_width_m": "m",
    "press_distance_m": "m",
    "distance_covered_km": "km",
    "progressive_passes": "count",
    "ppda": "ratio",
    "xa": "xg",
    "field_tilt_pct": "pct",
}


class StatRef(Model):
    metric: StatMetric
    team: Side
    window: MinuteWindow
    player_id: str | None = None              # set for player-level stats in focus-player mode


class Claim(Model):
    value: float
    unit: StatUnit
    stat_ref: StatRef
