"""Stat vocabulary and the references that tie every number the AI writes to a recomputable stat."""

from __future__ import annotations

from typing import Literal

from .common import MinuteWindow, Model, Side

# First version of the 15-stat vocabulary. D02 owns the wording and B05 owns the
# calculation; both must match this list exactly.
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
]

StatUnit = Literal["count", "pct", "xg", "index"]

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
