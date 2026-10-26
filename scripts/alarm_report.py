#!/usr/bin/env python3
"""How the momentum alarm (B06) behaves over N simulated matches, plus a picture of a few curves.

Usage: uv run --with matplotlib scripts/alarm_report.py [--matches 30] [--plot alarms.png]
Matches are the demo preset with its two planted events (38' red card, 63' substitution), as
in scripts/momentum_tune.py (B06-opta). Reports candidates per match, how many sit near a goal /
red card / substitution, and how many goals were followed by an alarm within 8 minutes.
"""
from __future__ import annotations

import argparse
import sys

import numpy as np

from pivot_core.analytics import detect_candidates, momentum_series
from pivot_core.sim import DEMO_1021, simulate


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=30)
    ap.add_argument("--plot", default=None)
    args = ap.parse_args()
    counts, with_key, goals, goals_hit, kept = [], 0, 0, 0, []
    for n in range(args.matches):
        out = simulate(DEMO_1021.build(900 + n), plants=list(DEMO_1021.plants))
        ev = out.events_as_models()
        ms = momentum_series(out.match.match_id, ev)
        cands = detect_candidates(out.match.match_id, ms, ev)
        counts.append(len(cands))
        with_key += sum(bool(c.key_event_ids) for c in cands)
        goal_min = [e.minute for e in ev if e.type == "shot" and e.shot_outcome == "goal"]
        goals += len(goal_min)
        goals_hit += sum(any(0 <= c.minute - g <= 8 or 0 <= g - c.minute <= 2 for c in cands) for g in goal_min)
        if len(kept) < 4:
            kept.append((out, ms, cands, ev))
    total = sum(counts)
    print(f"{args.matches} matches: {np.mean(counts):.1f} candidates per match, distribution {np.bincount(counts)}")
    print(f"candidates with a goal, red card or substitution in their window: {with_key}/{total} ({with_key / max(total, 1):.0%})")
    print(f"goals followed by an alarm within 8 minutes: {goals_hit}/{goals} ({goals_hit / max(goals, 1):.0%})")
    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(len(kept), 1, figsize=(12, 2.6 * len(kept)), sharex=True)
        for ax, (out, ms, cands, ev) in zip(np.atleast_1d(axes), kept):
            x = [m.minute for m in ms]
            y = [m.momentum for m in ms]
            ax.fill_between(x, y, 0, where=np.array(y) > 0, color="#1E6B45", alpha=0.6, label="home on top")
            ax.fill_between(x, y, 0, where=np.array(y) < 0, color="#d9534f", alpha=0.6, label="away on top")
            for e in ev:
                if e.type == "shot" and e.shot_outcome == "goal":
                    ax.axvline(e.minute, color="black", lw=1.2)
                    ax.text(e.minute, 0.9, "G" if e.team == "home" else "g", ha="center", fontsize=9)
                elif e.type == "card" and e.foul and e.foul.card in ("red", "second_yellow"):
                    ax.axvline(e.minute, color="red", lw=1.2, ls="--")
                elif e.type == "substitution":
                    ax.axvline(e.minute, color="grey", lw=0.6, ls=":")
            for c in cands:
                ax.annotate("▼", (c.minute, 1.0), ha="center", color="#4A1D57", fontsize=13)
            s = out.match.score
            ax.set_ylim(-1.1, 1.15)
            ax.set_title(f"{out.match.match_id}  {s.home}-{s.away}   ▼ alarm, | goal (G home, g away), red dashed = red card, dotted = sub", fontsize=9)
        np.atleast_1d(axes)[-1].set_xlabel("elapsed minute")
        fig.tight_layout()
        fig.savefig(args.plot, dpi=80)
        print("wrote", args.plot)


if __name__ == "__main__":
    main()
