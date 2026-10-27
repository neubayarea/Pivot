#!/usr/bin/env python3
"""What coach styles (Bx13) do to results: the site's matches without and with them, and 3-5-2.

  uv run scripts/styles_report.py                # the 20 site matches, then 120 paired 3-5-2 seeds
  uv run scripts/styles_report.py --pairs 240

For each site match: both coaches' styles, the score and the number of pivot candidates without
styles (today's site) and with them. Then 3-5-2 against 4-3-3 at equal strength, each way round,
with and without styles: wins, draws and losses of the 3-5-2 side.
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor

from pivot_api.sims import specs_first
from pivot_core.analytics import detect_candidates, momentum_series
from pivot_core.sim import build_demo_match, simulate
from pivot_core.sim.styles import style_of, with_coach_styles


def _site(spec) -> tuple:
    base = build_demo_match(spec.seed, spec.home_strength, spec.away_strength, spec.home_formation, spec.away_formation)
    row = [spec.match_id, style_of(spec.seed, "home"), style_of(spec.seed, "away")]
    for match in (base, with_coach_styles(base)):
        out = simulate(match)
        events = out.events_as_models()
        cands = detect_candidates(match.match_id, momentum_series(match.match_id, events), events)
        row += [f"{out.match.score.home}-{out.match.score.away}", len(cands)]
    return tuple(row)


def _three(job: tuple) -> tuple:
    seed, home352, styled = job
    m = build_demo_match(seed, 71, 71, "3-5-2" if home352 else "4-3-3", "4-3-3" if home352 else "3-5-2")
    s = simulate(with_coach_styles(m) if styled else m).match.score
    mine, theirs = (s.home, s.away) if home352 else (s.away, s.home)
    return home352, styled, (mine > theirs) - (mine < theirs)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--pairs", type=int, default=120)
    ap.add_argument("--seed", type=int, default=3000)
    args = ap.parse_args()
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(_site, specs_first(args.count)))
        print(f"{'match':12} {'home style':11} {'away style':11} {'without':>8} {'pivots':>6}  {'with':>6} {'pivots':>6}")
        for r in rows:
            print(f"{r[0]:12} {r[1]:11} {r[2]:11} {r[3]:>8} {r[4]:>6}  {r[5]:>6} {r[6]:>6}")
        for label, i in (("without", 3), ("with", 5)):
            res = [tuple(map(int, r[i].split("-"))) for r in rows]
            h = sum(a > b for a, b in res)
            d = sum(a == b for a, b in res)
            piv = [r[i + 1] for r in rows]
            print(f"{label:8} home/draw/away {h}/{d}/{len(res) - h - d}  pivots per match {sum(piv) / len(piv):.1f} "
                  f"(min {min(piv)}, max {max(piv)}, outside 1-3: {sum(p < 1 or p > 3 for p in piv)})")
        jobs = [(s, home, styled) for s in range(args.seed, args.seed + args.pairs) for home in (True, False)
                for styled in (False, True)]
        out = list(pool.map(_three, jobs, chunksize=4))
    for styled in (False, True):
        res = [r for _, st, r in [(h, s, x) for h, s, x in out] if st == styled]
        w, d, lo = res.count(1), res.count(0), res.count(-1)
        print(f"3-5-2 v 4-3-3, equal strength, {'with' if styled else 'without'} styles: "
              f"win {100 * w / len(res):.0f}%  draw {100 * d / len(res):.0f}%  lose {100 * lo / len(res):.0f}%  ({len(res)} matches)")


if __name__ == "__main__":
    main()
