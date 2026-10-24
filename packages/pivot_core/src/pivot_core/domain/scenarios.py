"""What-if scenarios, planted events and simulation results."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import Minute, Model, Side
from .lineup import TeamSheet, TeamTactics
from .narrative import Narrative

Probability = Annotated[float, Field(ge=0, le=1)]

ScenarioType = Literal[
    "cancel_substitution", "move_substitution", "remove_red_card", "remove_goal", "change_press",
    "change_formation", "change_tactics", "change_lineup",
]


class ScenarioSpec(Model):
    type: ScenarioType
    pivot_id: str
    target_event_id: str | None = None
    at_minute: Minute                         # resume from this minute's snapshot
    team: Side | None = None                  # side whose sheet or tactics change
    team_sheet: TeamSheet | None = None       # change_formation, change_lineup
    tactics: TeamTactics | None = None        # change_press, change_tactics
    params: dict[str, int | str] = {}
    n_runs: Literal[200, 500, 1000] = 500
    seed_base: int                            # run i uses seed_base + i for both arms


class PlantSpec(Model):
    """Force an event at a given minute. Used by the eval seeds and the demo preset."""

    minute: Minute
    type: Literal["red_card", "substitution", "goal", "press_change", "formation_change", "injury"]
    team: Side
    params: dict[str, int | str] = {}


OutcomeKey = Literal["home_win", "draw", "away_win", "home_advance"]


class OutcomeDist(Model):
    """Result after 90 minutes, plus who goes through when extra time and penalties apply."""

    home_win: Probability
    draw: Probability
    away_win: Probability
    home_advance: Probability | None = None   # knockout ties only: share of runs the home side went through
    ci95: dict[OutcomeKey, tuple[Probability, Probability]]  # Wilson


class SimResult(Model):
    scenario_id: str
    baseline: OutcomeDist
    counterfactual: OutcomeDist
    significant: dict[OutcomeKey, bool]   # True only if CIs do not overlap
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
