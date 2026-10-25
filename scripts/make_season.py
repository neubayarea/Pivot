#!/usr/bin/env python3
"""Play the fictional league season up to the demo (B13) and keep the results.

  uv run scripts/make_season.py           # matchdays 1-29 and the four earlier meetings, ~3 minutes

The demo match (matchday 30, the demo seed) is not played here: it is the recorded demo itself. The
output, eval/fixtures/season-2026.json, holds scores, scorers, red cards and substitutions only
(no events, no frames). scripts/make_demo.py reads it to give the demo match its form, table,
head-to-head, careers and news (pivot_core.sim.season).
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from pivot_core.sim.season import SEASON_FILE, play
from pivot_core.sim.world import DEMO_MATCHDAY, SEASON, WORLD_SEED, past_meetings, schedule

OUT = Path(__file__).resolve().parents[1] / "eval" / "fixtures" / SEASON_FILE


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    season = [f for f in schedule() if f.matchday < DEMO_MATCHDAY]
    earlier = past_meetings()
    with ProcessPoolExecutor() as pool:
        results = list(pool.map(play, season + earlier, chunksize=4))
    data = {"world_seed": WORLD_SEED, "season": SEASON, "demo_matchday": DEMO_MATCHDAY,
            "results": results[:len(season)], "past_meetings": results[len(season):]}
    text = json.dumps(data, separators=(",", ":"))
    OUT.write_text(text.replace('},{"season"', '},\n{"season"') + "\n", encoding="utf-8")   # one match per line
    print(f"wrote {OUT.relative_to(OUT.parents[2])}: {len(season)} league matches, {len(earlier)} earlier meetings")


if __name__ == "__main__":
    main()
