#!/usr/bin/env python3
"""Run N simulated matches and compare the averages with the PRD 6.3 calibration targets.

Usage: uv run scripts/sim_report.py [--matches 50] [--seed 1]
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from collections import Counter

import numpy as np

from pivot_core.sim import build_demo_match, simulate

# metric: (low, high) per match unless noted. From PRD 6.3.
TARGETS = {
    "goals": (2.5, 3.0),
    "shots": (20, 28),
    "shots_on_target": (7, 10),
    "xg_per_shot": (0.09, 0.12),
    "passes": (850, 1100),
    "pass_accuracy_pct": (75, 85),
    "avg_pass_length_m": (15, 22),
    "pressures": (300, 400),
    "fouls": (18, 26),
    "yellow_cards": (3, 5),
    "red_cards": (0, 0.15),
    "corners": (8, 12),
    "offsides": (3, 5),
    "distance_per_outfield_km": (9, 12),
    "added_time_1st_min": (1, 4),
    "added_time_2nd_min": (3, 8),
    "home_possession_pct": (35, 65),
}


def summarise(out) -> dict:
    ev = out.events
    c = Counter(e["type"] for e in ev)
    shots = [e for e in ev if e["type"] == "shot"]
    passes = [e for e in ev if e["type"] == "pass" and e.get("pass_type") != "throw_in"]
    cards = [e for e in ev if e["type"] == "card"]
    corners = sum(1 for e in ev if e["type"] == "pass" and e.get("pass_type") == "corner")
    lengths = [math.dist(e["location"], e["end_location"]) for e in passes if e.get("end_location")]
    poss = out.frames_possession
    live = poss >= 0
    outfield = []
    for k in (0, 1):
        for i in range(11):
            dist = float(out.frames_speed[:, k, i].sum())
            if dist > 3000:
                outfield.append(dist / 1000)
    added = {p.period: p.added_minutes for p in out.match.periods}
    s = out.match.score
    counters = len({e["possession_id"] for e in ev if e.get("play_pattern") == "counter"})
    return {
        "goals": s.home + s.away,
        "shots": len(shots),
        "shots_on_target": sum(e["shot_outcome"] in ("goal", "saved") for e in shots),
        "xg_per_shot": float(np.mean([e["xg"] for e in shots])) if shots else 0.0,
        "passes": len(passes),
        "pass_accuracy_pct": 100 * np.mean([e["outcome"] == "success" for e in passes]) if passes else 0.0,
        "avg_pass_length_m": float(np.mean(lengths)) if lengths else 0.0,
        "pressures": c["pressure"],
        "fouls": c["foul"],
        "yellow_cards": sum(e["foul"]["card"] == "yellow" for e in cards),
        "red_cards": sum(e["foul"]["card"] in ("red", "second_yellow") for e in cards),
        "corners": corners,
        "offsides": c["offside"],
        "distance_per_outfield_km": float(np.mean(outfield)) if outfield else 0.0,
        "added_time_1st_min": added.get(1) or 0,
        "added_time_2nd_min": added.get(2) or 0,
        "home_possession_pct": 100 * float(np.mean(poss[live] == 0)) if live.any() else 0.0,
        # reported, no target
        "tackles": c["tackle"],
        "duels": c["duel"],
        "dribbles": c["dribble"],
        "interceptions": c["interception"],
        "counters": counters,
        "effective_play_min": float(live.sum()) / 60,
        "events": len(ev),
        "throw_ins": sum(1 for e in ev if e["type"] == "pass" and e.get("pass_type") == "throw_in"),
        "goal_kicks": sum(1 for e in ev if e["type"] == "pass" and e.get("pass_type") == "goal_kick"),
        "free_kicks": sum(1 for e in ev if e["type"] == "pass" and e.get("pass_type") == "free_kick"),
        "max_jump_m": float(np.max(np.hypot(*np.diff(out.frames_pos, axis=0).transpose(3, 0, 1, 2)))),
        "_result": "H" if s.home > s.away else ("A" if s.away > s.home else "D"),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=50)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rows, results, secs = [], Counter(), []
    for n in range(args.matches):
        m = build_demo_match(args.seed + n)
        t0 = time.time()
        out = simulate(m)
        secs.append(time.time() - t0)
        r = summarise(out)
        results[r.pop("_result")] += 1
        rows.append(r)
    keys = list(rows[0])
    print(f"{args.matches} matches, {np.mean(secs):.2f} s per match\n")
    print(f"{'metric':28} {'mean':>9} {'sd':>7}   target          ok")
    for key in keys:
        vals = np.array([r[key] for r in rows], dtype=float)
        lo_hi = TARGETS.get(key)
        mark, tgt = "", ""
        if lo_hi:
            tgt = f"{lo_hi[0]:g}–{lo_hi[1]:g}"
            mark = "✓" if lo_hi[0] <= vals.mean() <= lo_hi[1] else "✗"
        print(f"{key:28} {vals.mean():9.2f} {vals.std():7.2f}   {tgt:14}  {mark}")
    total = sum(results.values())
    print(f"\nresults: home {100 * results['H'] / total:.0f}%  draw {100 * results['D'] / total:.0f}%  "
          f"away {100 * results['A'] / total:.0f}%   (target ~45 / 25 / 30)")


if __name__ == "__main__":
    main()
