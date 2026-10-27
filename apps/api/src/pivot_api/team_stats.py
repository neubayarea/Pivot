"""The team stats of a match (Bx11): MET-001 to MET-023 for both teams, with what the page labels them.

GET /api/matches/{id}/stats[?scope=match|first_half|second_half|extra_time_1|extra_time_2]
                           [?from=<minute>&to=<minute>][&up_to=<seconds>]

- The numbers are B05's StatCalculator, the same ones the AI cites and the Verifier checks, laid
  out like the recorded demo's `team_stats` (pivot_core.analytics.team_stats): the whole match,
  then each period cut at its whistle, extra time when it was played.
- `up_to` counts only what happened by that elapsed second, for a replay or a live match.
- `from` / `to` ask for one window of elapsed minutes instead (from <= minute < to).
- A stat with no answer (no tracking frames, nothing to divide by) is null, never 0.
- Every stat comes with its MET id, unit, decimals, group, analyst and fan label (the D02
  vocabulary in pivot_worker.vocabulary), so the page hard-codes nothing. English only for now.

Read-only. A finished match's table is kept in memory after the first request.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, Request

from pivot_core.analytics import MET_IDS, team_stats
from pivot_core.analytics.stats import DECIMALS
from pivot_core.analytics.team_stats import stat_row
from pivot_core.domain import STAT_UNITS, StatMetricInfo, StatScope, TeamStatsReport, TeamStatsScope
from pivot_worker.vocabulary import STAT_TERMS

from . import matchdata

router = APIRouter(prefix="/api")

# Display groups, in order, like the Premier League site's Attack / Possession / Defence / Physical.
# "shape" is ours: where the team stood, from the tracking frames.
GROUPS: dict[str, tuple[str, ...]] = {
    "attack": ("shots", "shots_on_target", "xg", "xa", "box_entries", "threat_total"),
    "possession": ("possession_pct", "passes", "pass_accuracy_pct", "passes_final_third", "progressive_passes",
                   "field_tilt_pct", "turnovers", "momentum_avg"),
    "defence": ("tackles_won", "interceptions", "duels_won", "pressures", "ppda"),
    "shape": ("line_height_m", "team_width_m", "press_distance_m"),
    "physical": ("distance_covered_km",),
}


def metric_info() -> list[StatMetricInfo]:
    """The 23 stats in display order, with their labels."""
    out = []
    for group, metrics in GROUPS.items():
        for m in metrics:
            term, unit = STAT_TERMS[m], STAT_UNITS[m]
            out.append(StatMetricInfo(metric=m, definition_id=MET_IDS[m], unit=unit, decimals=DECIMALS[unit],
                                      group=group, label=term.label, fan_label=term.fan_label,
                                      description=term.definition, higher_means=term.higher_means))
    return out


METRICS = metric_info()


@router.get("/matches/{match_id}/stats")
async def match_stats(request: Request, match_id: str, scope: StatScope | None = None,
                      start: int | None = Query(None, alias="from", ge=0, le=180),
                      end: int | None = Query(None, alias="to", ge=1, le=181),
                      up_to: int | None = Query(None, ge=0)) -> TeamStatsReport:
    """Both teams' 23 stats for the whole match and each period (or `scope` only, or the
    `from`-`to` minute window), up to `up_to` elapsed seconds (default: everything so far).

    404 for an unknown match; 422 for a window that ends before it starts, or `scope=window` without one.
    """
    match = await request.app.state.adapters.matches.get_match(match_id)
    if match is None:
        raise HTTPException(404, f"match {match_id!r} not found")
    window = None
    if start is not None or end is not None or scope == "window":
        if start is None or end is None or end <= start:
            raise HTTPException(422, "a window needs from < to, in elapsed minutes")
        window = (start, end)

    events, frames = await matchdata.inputs(request, match)
    last = matchdata.last_second(match, events, frames)
    cut = None if up_to is None or up_to >= last else up_to
    calc = await matchdata.calculator(request, match, cut)
    covered = last if cut is None else cut
    finished = match.status == "finished" and cut is None

    cache = matchdata.shared(request, "team_stats", dict) if finished else {}
    key = (match_id, window)
    if key not in cache:
        if window is not None:
            rows = [await asyncio.to_thread(stat_row, calc, "window", None, window)]
        else:
            rows = await asyncio.to_thread(team_stats, calc, cut)
        cache[key] = [TeamStatsScope(scope=r["scope"], period=r["period"], window=tuple(r["window"]),
                                     home=r["home"], away=r["away"]) for r in rows]
    scopes = [s for s in cache[key] if scope is None or s.scope == scope]
    return TeamStatsReport(match_id=match_id, up_to_t=covered, metrics=METRICS, scopes=scopes)
