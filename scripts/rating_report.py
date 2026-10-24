#!/usr/bin/env python3
"""Rating distribution over N simulated matches, by position group (RAT-001 calibration).

Usage: uv run scripts/rating_report.py [--matches 30]
Target (data definitions, section 5): overall mean about 6.7, sd about 0.7, and every
position group between 6.6 and 6.8. Players with fewer than 10 minutes are left out.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict

import numpy as np

from pivot_core.analytics import StatCalculator, player_match_stats
from pivot_core.sim import build_demo_match, simulate


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=30)
    args = ap.parse_args()
    groups = defaultdict(list)
    scorers = []
    for n in range(args.matches):
        m = build_demo_match(500 + n)
        position = {p.player_id: p.position for t in (m.home, m.away) for p in t.squad}
        calc = StatCalculator.from_sim(simulate(m))
        for s in player_match_stats(calc):
            if s.minutes_played < 10:
                continue
            groups[position[s.player_id]].append(s.rating)
            groups["ALL"].append(s.rating)
            if s.goals:
                scorers.append(s.rating)
    print(f"{'group':6} {'n':>5} {'mean':>6} {'sd':>5} {'min':>5} {'max':>5}")
    for g in ("GK", "DF", "MF", "FW", "ALL"):
        v = np.array(groups[g])
        print(f"{g:6} {len(v):5d} {v.mean():6.2f} {v.std():5.2f} {v.min():5.1f} {v.max():5.1f}")
    print(f"\nscorers: mean {np.mean(scorers):.2f}, share at 7.5 or above {np.mean(np.array(scorers) >= 7.5):.0%}")


if __name__ == "__main__":
    main()
