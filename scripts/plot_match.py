#!/usr/bin/env python3
"""Draw snapshots of a simulated match: player positions at several moments plus a shot map.

Usage: uv run --with matplotlib scripts/plot_match.py [--seed 1021] [--out match.png]
"""
from __future__ import annotations

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from pivot_core.sim import build_demo_match, simulate  # noqa: E402


def pitch(ax):
    ax.set_xlim(-2, 107)
    ax.set_ylim(-2, 70)
    ax.set_aspect("equal")
    ax.set_facecolor("#3a7d44")
    lc = "white"
    ax.plot([0, 105, 105, 0, 0], [0, 0, 68, 68, 0], color=lc, lw=1)
    ax.plot([52.5, 52.5], [0, 68], color=lc, lw=1)
    ax.add_patch(plt.Circle((52.5, 34), 9.15, fill=False, color=lc, lw=1))
    for x0, s in ((0, 1), (105, -1)):
        ax.plot([x0, x0 + s * 16.5, x0 + s * 16.5, x0], [13.84, 13.84, 54.16, 54.16], color=lc, lw=1)
        ax.plot([x0, x0 + s * 5.5, x0 + s * 5.5, x0], [24.84, 24.84, 43.16, 43.16], color=lc, lw=1)
    ax.set_xticks([])
    ax.set_yticks([])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1021)
    ap.add_argument("--out", default="match.png")
    args = ap.parse_args()
    out = simulate(build_demo_match(args.seed))
    fig, axes = plt.subplots(3, 3, figsize=(15, 10.5))
    live = np.flatnonzero(out.frames_possession >= 0)
    picks = live[np.linspace(len(live) * 0.05, len(live) * 0.95, 8).astype(int)]
    colors = ("#f2f2f2", "#d9534f")
    for ax, n in zip(axes.flat[:8], picks):
        pitch(ax)
        for k in (0, 1):
            ids = out.frames_ids[n][k]
            pts = np.array([out.frames_pos[n, k, i] for i, p in enumerate(ids) if p])
            ax.scatter(pts[:, 0], pts[:, 1], s=60, c=colors[k], edgecolors="black", zorder=3)
        bx, by, _ = out.frames_ball[n]
        ax.scatter([bx], [by], s=25, c="yellow", edgecolors="black", zorder=4)
        side = ("home", "away")[int(out.frames_possession[n])]
        ax.set_title(f"t={int(out.frames_t[n]) // 60}'  ball: {side}  (home white attacks →)", fontsize=9)
    ax = axes.flat[8]
    pitch(ax)
    for e in out.events:
        if e["type"] == "shot":
            x, y = e["location"]
            c = colors[0] if e["team"] == "home" else colors[1]
            ax.scatter([x], [y], s=400 * e["xg"] + 10, c=c, edgecolors="black",
                       marker="*" if e["shot_outcome"] == "goal" else "o", zorder=3)
    s = out.match.score
    ax.set_title(f"shots (size = xG, star = goal)   {s.home}-{s.away}", fontsize=9)
    fig.tight_layout()
    fig.savefig(args.out, dpi=80)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
