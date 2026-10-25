#!/usr/bin/env python3
"""What-if on the demo match (the demo-1021 preset): win/draw/loss with and without one change, and how long it takes.

  uv run scripts/whatif_report.py                      # both scenarios, 200 runs per arm
  uv run scripts/whatif_report.py --n 200 500 1000     # runtime at each size
  uv run scripts/whatif_report.py --only red --workers 8

Scenarios:
  press  Harbour City keep their press and line at 63' instead of dropping deep (the substitution
         still happens). Expected: Rovers come back less often, Harbour City hold on more.
  red    The 38' red card is not given. Expected: Rovers clearly better off.
  cancel The 63' change (h15 for h09 and drop deep) is not made.
  goal   Harbour City's goal is ruled out.
"""
from __future__ import annotations

import argparse
import sys
import time

from pivot_core.domain import ScenarioSpec, TeamTactics
from pivot_core.sim import DEMO_1021, simulate
from pivot_core.sim.whatif import run_whatif


def specs(events: list[dict]) -> dict[str, tuple[str, ScenarioSpec]]:
    red = next(e for e in events if e["type"] == "card" and e["foul"]["card"] == "red")
    sub = next(e for e in events if e["type"] == "substitution" and e["substitution"]["reason"] == "tactical")
    goal = next(e for e in events if e["type"] == "shot" and e["shot_outcome"] == "goal")
    before = DEMO_1021.build().home.tactics          # mid line, mid press until 63'

    def spec(type_, e, **kw):
        return ScenarioSpec(type=type_, pivot_id="demo", target_event_id=e["event_id"], at_minute=e["t"] // 60,
                            team=e["team"], seed_base=10_000, **kw)

    return {
        "press": ("Harbour City keep press and line at 63'",
                  spec("change_tactics", sub, tactics=TeamTactics(**before.model_dump()))),
        "red": ("No red card at 38'", spec("remove_red_card", red)),
        "cancel": ("No 63' change", spec("cancel_substitution", sub)),
        "goal": ("Harbour City goal ruled out", spec("remove_goal", goal)),
    }


def pct(d, key: str) -> str:
    lo, hi = d.ci95[key]
    return f"{getattr(d, key) * 100:5.1f}% [{lo * 100:4.1f}-{hi * 100:4.1f}]"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, nargs="+", default=[200], help="runs per arm")
    ap.add_argument("--only", nargs="+", default=["press", "red"], choices=["press", "red", "cancel", "goal"])
    ap.add_argument("--workers", type=int, default=None, help="processes (default: all cores)")
    args = ap.parse_args()

    t0 = time.perf_counter()
    events = simulate(DEMO_1021.build(), plants=list(DEMO_1021.plants)).events
    print(f"demo match simulated once to find the events: {time.perf_counter() - t0:.1f} s")
    table = specs(events)
    for name in args.only:
        label, sp = table[name]
        print(f"\n== {label}  ({sp.type}, from minute {sp.at_minute}) ==")
        print(f"{'runs/arm':>8}  {'arm':<15} {'Harbour City win':<24} {'draw':<24} {'Rovers win':<24} time")
        for n in args.n:
            res = run_whatif(DEMO_1021.build(), sp, plants=DEMO_1021.plants, workers=args.workers, n_runs=n)
            for arm, d in (("as played", res.baseline), ("changed", res.counterfactual)):
                t = f"{res.runtime_ms / 1000:.1f} s" if arm == "changed" else ""
                print(f"{n:>8}  {arm:<15} {pct(d, 'home_win'):<24} {pct(d, 'draw'):<24} {pct(d, 'away_win'):<24} {t}")
            sig = [k for k, v in res.significant.items() if v]
            print(f"{'':>8}  significant: {', '.join(sig) or 'none'}")


if __name__ == "__main__":
    main()
