#!/usr/bin/env python3
"""Fingerprint simulated matches, to prove that a change leaves the run of play untouched.

  uv run scripts/sim_fingerprint.py > before.txt     # on main
  uv run scripts/sim_fingerprint.py > after.txt      # on your branch
  diff before.txt after.txt                          # no output: every match plays exactly as before

One line per match: the score, the number of events, then short hashes of the events, the player
positions and the rest of the tracking frames (ball, possession, speeds, fitness, who is on).
Covers seeds 1-20 and 41, and the demo preset with its planted red card and substitution (seed 41
plus two more seeds). A speed-up must not change a single line; a new rule (B12, B14) will, and
its PR has to say so. Seconds per match go to stderr, so they never show up in the diff.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time

import numpy as np

from pivot_core.sim import DEMO_1021, build_demo_match, simulate


def _json(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return repr(o)


def _hash(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.hexdigest()[:16]


def _arrays(*arrays: np.ndarray) -> bytes:
    return b"".join(f"{a.dtype}{a.shape}".encode() + np.ascontiguousarray(a).tobytes() for a in arrays)


def fingerprint(out) -> str:
    s = out.match.score
    events = _hash(json.dumps(out.events, sort_keys=True, default=_json).encode())
    pos = _hash(_arrays(out.frames_pos))
    rest = _hash(_arrays(out.frames_t, out.frames_period, out.frames_possession, out.frames_ball,
                         out.frames_speed, out.frames_fitness),
                 json.dumps([out.frames_owner, out.frames_ids]).encode())
    return f"{s.home}-{s.away} events={len(out.events)} ev:{events} pos:{pos} frames:{rest}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="*", default=list(range(1, 21)) + [41])
    ap.add_argument("--preset-seeds", type=int, nargs="*", default=[41, 7, 300])
    args = ap.parse_args()
    runs = [(f"seed {s}", build_demo_match(s), None) for s in args.seeds]
    runs += [(f"demo-1021 seed {s}", DEMO_1021.build(s), list(DEMO_1021.plants)) for s in args.preset_seeds]
    secs = []
    for name, match, plants in runs:
        t0 = time.perf_counter()
        out = simulate(match, plants=plants)
        secs.append(time.perf_counter() - t0)
        print(f"{name:20} {fingerprint(out)}", flush=True)
    print(f"{len(secs)} matches, {np.mean(secs):.2f} s per match", file=sys.stderr)


if __name__ == "__main__":
    main()
