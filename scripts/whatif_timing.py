#!/usr/bin/env python3
"""Bx10: what counting the per-run numbers costs, on the demo's red-card scenario, in one process.

  uv run scripts/whatif_timing.py            # 200 runs per arm, both ways
  uv run scripts/whatif_timing.py --n 20

Each run is played twice from the same start and seed: once as before Bx10 (`play_on`, final
score only) and once counted (`play_counted`). The two are interleaved so a busy machine slows
both alike. The final scores must come out the same.
"""
from __future__ import annotations

import argparse
import sys
import time

from whatif_report import specs

from pivot_core.sim import DEMO_1021, simulate
from pivot_core.sim.whatif import _score, play_counted, play_on, prepare, save


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200, help="runs per arm")
    args = ap.parse_args()

    events = simulate(DEMO_1021.build(), plants=list(DEMO_1021.plants)).events
    _, sp = specs(events)["red"]
    starts = prepare(save(DEMO_1021.build(), sp.at_minute, plants=DEMO_1021.plants), sp)
    plain = counted = 0.0
    for i in range(args.n):
        seed = sp.seed_base + i
        for start in starts:
            t0 = time.perf_counter()
            old = _score(play_on(start, seed))
            t1 = time.perf_counter()
            new = play_counted(start, seed)
            t2 = time.perf_counter()
            plain, counted = plain + t1 - t0, counted + t2 - t1
            if new.score != old:
                raise SystemExit(f"seed {seed}: score {new.score} counted, {old} before")
    runs = 2 * args.n
    print(f"{runs} runs from minute {sp.at_minute}, all final scores the same both ways")
    print(f"before (score only): {plain:7.1f} s  {plain / runs * 1000:6.0f} ms a run")
    print(f"counted:             {counted:7.1f} s  {counted / runs * 1000:6.0f} ms a run")
    print(f"extra cost:          {(counted / plain - 1) * 100:+6.1f} %")


if __name__ == "__main__":
    main()
