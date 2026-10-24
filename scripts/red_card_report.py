#!/usr/bin/env python3
"""How much does a red card change a match? Plant one at 38' and compare with the same seeds without it.

  uv run scripts/red_card_report.py            # 24 seeds
  uv run scripts/red_card_report.py --n 60

Real football (rough consensus): with a man more, a side takes about 60-70 % of the shots.
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from pivot_core.domain import PlantSpec
from pivot_core.sim import build_demo_match, simulate

RED = PlantSpec(minute=38, type="red_card", team="away")


def one(args: tuple[bool, int]) -> tuple[bool, int, int, int, int]:
    planted, seed = args
    out = simulate(build_demo_match(seed), plants=[RED] if planted else [])
    after = [e for e in out.events_as_models()
             if e.type == "shot" and e.period in (1, 2) and (e.period == 2 or e.period_t >= 37 * 60)]
    s = out.match.score
    return planted, sum(e.team == "home" for e in after), sum(e.team == "away" for e in after), s.home, s.away


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--start", type=int, default=500)
    args = ap.parse_args()
    jobs = [(p, s) for p in (False, True) for s in range(args.start, args.start + args.n)]
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(one, jobs))
    for planted in (False, True):
        r = np.array([x[1:] for x in rows if x[0] == planted])
        label = "away red at 38'" if planted else "no red card    "
        print(f"{label}  shots after 38': home {r[:, 0].mean():4.1f}  away {r[:, 1].mean():4.1f}  "
              f"home share {r[:, 0].sum() / max(r[:, :2].sum(), 1):.2f}   goals {r[:, 2].mean():.2f}-{r[:, 3].mean():.2f}")


if __name__ == "__main__":
    main()
