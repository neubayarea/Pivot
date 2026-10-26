#!/usr/bin/env python3
"""How much the planted red card (38') and substitution (63') move momentum, old vs new, on
matches cached by scripts/momentum_cache.py, in units of each series' own spread.

  uv run scripts/momentum_plants.py --cache .pivot-data/momentum-cache.pkl
"""
from __future__ import annotations

import argparse
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from pivot_core.analytics import momentum_series

sys.path.insert(0, str(Path(__file__).resolve().parent))
from momentum_tune import DEMO_SEED, old_series, plant_minutes  # noqa: E402


def swing(m, t, w):
    return m[t:t + w].mean() - m[max(0, t - w):t].mean()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=".pivot-data/momentum-cache.pkl")
    ap.add_argument("--window", type=int, default=8)
    args = ap.parse_args()
    data = pickle.loads(Path(args.cache).read_bytes())
    res = {"old": defaultdict(list), "new": defaultdict(list)}
    for seed, mid, ev in data:
        red, sub = plant_minutes(ev)
        for name, m in (("old", old_series(ev)), ("new", np.array([x.momentum for x in momentum_series(mid, ev)]))):
            sd = m.std()
            for label, t in (("red", red), ("sub", sub)):
                if t is None:
                    continue
                s = swing(m, t, args.window)
                if seed == DEMO_SEED:
                    print(f"demo {name} {label} at {t}: swing {s:+.2f} ({s / sd:+.2f} sd)")
                else:
                    res[name][label].append(s / sd)
                    res[name][label + "_raw"].append(s)
            if seed != DEMO_SEED:
                res[name]["sd"].append(sd)
    for name, r in res.items():
        print(f"{name}: sd {np.mean(r['sd']):.2f}; red swing mean {np.mean(r['red_raw']):+.2f} "
              f"({np.mean(r['red']):+.2f} sd, towards home in {np.mean(np.array(r['red']) > 0):.0%}); "
              f"sub swing mean {np.mean(r['sub_raw']):+.2f} ({np.mean(r['sub']):+.2f} sd, "
              f"towards away in {np.mean(np.array(r['sub']) < 0):.0%})")


if __name__ == "__main__":
    main()
