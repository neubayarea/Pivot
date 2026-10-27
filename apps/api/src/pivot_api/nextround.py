"""The next round of the season (C14, #354): matchday 31's fixtures, not played yet, each with a
pre-match prediction.

- The matches are the season's own fixtures (`world.schedule`, `world.fixture_match`) with the
  pre-match context of the season so far, built the way `with_seed_season` builds a seed match's
  (form, head-to-head, news, conditions, context effects). Nothing in pivot_core changes.
- The prediction: each fixture played `N_RUNS` times from kick-off with the What-if runner
  (`run_arms`, the baseline arm only: nothing is changed), giving win / draw / loss with 95 %
  ranges, the likeliest scorelines and each team's expected goals.
- It is worked out ahead of time (`scripts/make_next_round.py`) into `eval/fixtures/next-round/`,
  like the precomputed What-ifs (#320, #343), so the 2-core server only reads it. The file names
  the simulator version it was computed with; a file from another version is not used, and the
  fixtures are then shown without a prediction.

At startup the API stores the fixtures as scheduled matches, so `/?match=S2026-31-…` opens their
Preview and Line-ups (#327's `/prematch` covers them through `prematch.matchday_of`).
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path

from pivot_core.domain import Match
from pivot_core.sim.effects import with_effects
from pivot_core.sim.season import _before, _story_team, _with_context, season_stats
from pivot_core.sim.whatif import run_arms, save, summarise
from pivot_core.sim.world import DEMO_MATCHDAY, HBC, ROV, Fixture, fixture_match, schedule

from . import sims

log = logging.getLogger(__name__)

NEXT_MATCHDAY = DEMO_MATCHDAY + 1
N_RUNS = 200
SHOWN = 5
TOP_SCORELINES = 3
PATH = Path(__file__).resolve().parents[4] / "eval" / "fixtures" / "next-round" / f"matchday-{NEXT_MATCHDAY}.json"


def fixtures(matchday: int = NEXT_MATCHDAY, shown: int = SHOWN) -> list[Fixture]:
    """The round's first `shown` fixtures, the site's two clubs' games first (a full match takes about
    15 s to play, so 200 plays of all ten would take the laptop most of an hour)."""
    ours = {HBC.club_id, ROV.club_id}
    round_ = sorted((fx for fx in schedule() if fx.matchday == matchday), key=lambda fx: not ({fx.home, fx.away} & ours))
    return round_[:shown]


def next_match(fx: Fixture, season: dict | None) -> Match:
    """The fixture before kick-off, with the context counted from the results before its matchday."""
    match = fixture_match(fx)
    if season is None:
        return match
    results = _before(season, fx.matchday)
    stats = season_stats(results)
    home, away = (_story_team(t, stats, fx.matchday - 1, {}, None) for t in (match.home, match.away))
    return with_effects(_with_context(match, season, results, stats, home, away, []))


def predict(match: Match, n_runs: int = N_RUNS, workers: int | None = None) -> dict:
    """`n_runs` plays from kick-off, run i on seed `match.seed * 1000 + i`: the outcome odds with their
    95 % ranges, the likeliest scorelines and the expected goals (mean xG per run)."""
    start = save(match, 0, match.seed)
    runs = run_arms([start], n_runs, seed_base=(match.seed or 0) * 1000, workers=workers)[0]
    dist = summarise([r.score for r in runs])
    scorelines = Counter(r.score for r in runs).most_common(TOP_SCORELINES)
    return {
        "n_runs": n_runs,
        "home_win": dist.home_win, "draw": dist.draw, "away_win": dist.away_win,
        "ci95": {k: list(v) for k, v in dist.ci95.items()},
        "scorelines": [{"home": h, "away": a, "share": round(n / n_runs, 3)} for (h, a), n in scorelines],
        "xg": {"home": round(sum(r.home[3] for r in runs) / n_runs, 2),
               "away": round(sum(r.away[3] for r in runs) / n_runs, 2)},
        "goals": {"home": round(sum(r.score[0] for r in runs) / n_runs, 2),
                  "away": round(sum(r.score[1] for r in runs) / n_runs, 2)},
    }


def read(path: Path, version: str) -> dict[str, dict]:
    """The predictions by match id, or none when the file is missing or from another simulator version."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("sim_version") != version:
        log.warning("%s was computed with simulator %s, not %s: next round shown without predictions",
                    path.name, data.get("sim_version"), version)
        return {}
    return {f["match_id"]: f["prediction"] for f in data["fixtures"]}


async def load_next_round(app_state, path: Path = PATH) -> list[str]:
    """Store the next round's fixtures as scheduled matches and keep their predictions for the hub."""
    from .whatif import portable_sim_version

    season = sims._season()
    matches = [next_match(fx, season) for fx in fixtures()]
    for m in matches:
        await app_state.adapters.matches.upsert_match(m)
    predictions = read(path, portable_sim_version())
    app_state.next_round = {"matchday": NEXT_MATCHDAY, "order": [m.match_id for m in matches], "predictions": predictions}
    log.info("next round: %d fixtures of matchday %d, %d with a prediction", len(matches), NEXT_MATCHDAY,
             len(predictions))
    return [m.match_id for m in matches]
