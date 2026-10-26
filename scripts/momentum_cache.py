#!/usr/bin/env python3
"""Simulate N demo-preset matches (with the plants) once and keep their events, for tuning
momentum and the alarm without re-running the simulator.

  uv run scripts/momentum_cache.py --matches 150 --out .pivot-data/momentum-cache.pkl
"""
from __future__ import annotations

import argparse
import pickle
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from pivot_core.sim import simulate
from pivot_core.sim.presets import DEMO_1021


def one(seed: int):
    out = simulate(DEMO_1021.build(seed), plants=list(DEMO_1021.plants))
    return seed, out.match.match_id, out.events_as_models()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=150)
    ap.add_argument("--start", type=int, default=1000)
    ap.add_argument("--out", default=".pivot-data/momentum-cache.pkl")
    args = ap.parse_args()
    seeds = list(range(args.start, args.start + args.matches)) + [DEMO_1021.seed]
    with ProcessPoolExecutor() as pool:
        res = list(pool.map(one, seeds))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_bytes(pickle.dumps(res))
    print(f"cached {len(res)} matches to {args.out}")


if __name__ == "__main__":
    main()
