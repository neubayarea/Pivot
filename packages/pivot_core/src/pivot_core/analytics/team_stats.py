"""The team-stats table: MET-001 to MET-023 for both teams, for the whole match and each period.

`team_stats(calc)` is what the recorded demo file keeps (scripts/make_demo.py) and what the API
serves (GET /api/matches/{id}/stats). Each period is cut at its whistle, as `compute(..., period=)`
does; extra time gets its own two rows when it was played. A value the definitions leave empty
(no frames, nothing to divide by) is None, never 0.
"""

from __future__ import annotations

from ..domain import STAT_UNITS, StatRef
from .stats import StatCalculator

SCOPE_OF_PERIOD = {1: "first_half", 2: "second_half", 3: "extra_time_1", 4: "extra_time_2"}
MET_IDS = {metric: f"MET-{n:03d}" for n, metric in enumerate(STAT_UNITS, start=1)}   # docs/data-definitions.md §4


def stat_row(calc: StatCalculator, scope: str, period: int | None, window: tuple[int, int]) -> dict:
    row: dict = {"scope": scope, "period": period, "window": list(window)}
    for team in ("home", "away"):
        values = {}
        for metric in STAT_UNITS:
            try:
                values[metric] = calc.compute(StatRef(metric=metric, team=team, window=window), period=period)
            except LookupError:                 # no data for it (no frames, nothing to divide by)
                values[metric] = None
        row[team] = values
    return row


def team_stats(calc: StatCalculator, up_to_t: int | None = None) -> list[dict]:
    """The whole match, then each period played, as rows of {scope, period, window, home, away}.

    With `up_to_t`, only the periods that had started by then, the last one cut there. Pass a
    calculator built from the events and frames up to that second, so nothing later counts.
    """
    periods = [p for p in calc.match.periods if p.period != 5 and (up_to_t is None or p.start_t <= up_to_t)]
    if not periods:
        return []

    def end(p) -> int:
        return p.end_t if up_to_t is None else min(p.end_t, up_to_t)

    scopes = [("match", None, (0, end(periods[-1]) // 60 + 1))]
    scopes += [(SCOPE_OF_PERIOD[p.period], p.period, (p.start_t // 60, end(p) // 60 + 1)) for p in periods]
    return [stat_row(calc, scope, period, window) for scope, period, window in scopes]
