"""What-if scenarios, planted events and simulation results."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field

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

    minute: Minute                            # scoreboard minute (63 = 63'), not elapsed minutes
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


class Spread(Model):
    """One number over all runs of an arm: its mean, standard deviation and 10th/90th percentiles."""

    mean: float
    sd: Annotated[float, Field(ge=0)]
    p10: float                                # one run in ten had this or less
    p90: float                                # one run in ten had this or more


class TeamRunStats(Model):
    """What one team did from the replay start to the end, over all runs of an arm (Bx10)."""

    goals: Spread
    shots: Spread
    shots_on_target: Spread
    xg: Spread
    possession_pct: Spread                    # 0-100, seconds with the ball in play
    cards: Spread                             # yellow and red
    red_cards: Spread                         # straight reds and second yellows
    scored_share: Probability                 # runs in which the team scored at least once


class ScoreShare(Model):
    home: Annotated[int, Field(ge=0)]
    away: Annotated[int, Field(ge=0)]
    share: Probability                        # of the arm's runs that ended with this score


class ArmStats(Model):
    """Why an arm came out as it did: its final scores and each team's numbers after the replay start."""

    n_runs: Annotated[int, Field(ge=1)]
    from_t: Annotated[int, Field(ge=0)]       # elapsed second the runs start from (the saved minute)
    top_scores: list[ScoreShare]              # most common final scores first, at most 5
    home: TeamRunStats
    away: TeamRunStats


STATS_FIELDS = ("baseline_stats", "counterfactual_stats")


def _stats_optional(schema: dict) -> None:
    """Results stored before Bx10 have no stats, so the frontend types must not count on them."""
    schema["required"] = [k for k in schema.get("required", []) if k not in STATS_FIELDS]


class SimResult(Model):
    model_config = ConfigDict(json_schema_extra=_stats_optional)

    scenario_id: str
    baseline: OutcomeDist
    counterfactual: OutcomeDist
    baseline_stats: ArmStats | None = None        # Bx10; None in results stored before it
    counterfactual_stats: ArmStats | None = None
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
