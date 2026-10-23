"""What-if scenarios, planted events and simulation results."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import Minute, Model, Side
from .narrative import Narrative

Probability = Annotated[float, Field(ge=0, le=1)]

ScenarioType = Literal[
    "cancel_substitution", "move_substitution", "remove_red_card", "remove_goal", "change_press",
]


class ScenarioSpec(Model):
    type: ScenarioType
    pivot_id: str
    target_event_id: str | None = None
    at_minute: Minute                         # resume from this minute's snapshot
    params: dict[str, int | str] = {}
    n_runs: Literal[200, 500, 1000] = 500
    seed_base: int                            # run i uses seed_base + i for both arms


class PlantSpec(Model):
    """Force an event at a given minute. Used by the eval seeds and the demo preset."""

    minute: Minute
    type: Literal["red_card", "substitution", "goal", "press_change"]
    team: Side
    params: dict[str, int | str] = {}


class OutcomeDist(Model):
    home_win: Probability
    draw: Probability
    away_win: Probability
    ci95: dict[Literal["home_win", "draw", "away_win"], tuple[Probability, Probability]]  # Wilson


class SimResult(Model):
    scenario_id: str
    baseline: OutcomeDist
    counterfactual: OutcomeDist
    significant: dict[Literal["home_win", "draw", "away_win"], bool]   # True only if CIs do not overlap
    narrative: Narrative | None = None        # Comparator output, default version
    runtime_ms: Annotated[int, Field(ge=0)]
    executor: Literal["local_pool", "aca_jobs"]


ScenarioStatus = Literal["queued", "running", "completed", "failed"]


class Scenario(Model):
    scenario_id: str                          # "{match_id}:s{uuid}"
    match_id: str
    spec: ScenarioSpec
    status: ScenarioStatus
    done: Annotated[int, Field(ge=0)] = 0     # finished runs, for the progress bar
    result: SimResult | None = None
