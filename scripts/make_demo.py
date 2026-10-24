#!/usr/bin/env python3
"""Build the demo-1021 fixture (B02) from the simulator.

  uv run scripts/make_demo.py --search 300        # try seeds, print the ones that tell the demo story
  uv run scripts/make_demo.py --seed 123          # export that seed to eval/fixtures/

A seed tells the story when, with the two planted events (38' red card for Rovers, 63' Harbour
City substitution and deeper line):
  - the alarm fires between 37' and 46' towards Harbour City,
  - Harbour City lead when the substitution comes,
  - the alarm fires between 62' and 70' towards Rovers,
  - the match has 1 to 4 goals and no red card other than the planted one.

Output (all fields follow packages/contracts):
  eval/fixtures/demo-1021.json           match, events, minute metrics, pivot candidates, player stats
  eval/fixtures/demo-1021.frames.json.gz one tracking frame per second
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from pivot_core.analytics import StatCalculator, detect_candidates, momentum_series, player_match_stats
from pivot_core.sim import simulate
from pivot_core.sim.presets import DEMO_1021

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "fixtures"


def run(seed: int):
    match = DEMO_1021.build(seed)
    out = simulate(match, plants=list(DEMO_1021.plants))
    events = out.events_as_models()
    metrics = momentum_series(match.match_id, events)
    cands = detect_candidates(match.match_id, metrics, events)
    return out, events, metrics, cands


def score_at(events, minute: int) -> tuple[int, int]:
    h = sum(1 for e in events if e.type == "shot" and e.shot_outcome == "goal" and e.team == "home" and e.minute < minute)
    a = sum(1 for e in events if e.type == "shot" and e.shot_outcome == "goal" and e.team == "away" and e.minute < minute)
    return h, a


def check(seed: int) -> tuple[int, bool, str]:
    out, events, _, cands = run(seed)
    sub = next((e for e in events if e.type == "substitution" and e.substitution.reason == "tactical"), None)
    sub_min = sub.minute if sub else 63
    early = [c for c in cands if 37 <= c.minute <= 46 and c.direction == "home"]
    late = [c for c in cands if sub_min - 1 <= c.minute <= sub_min + 7 and c.direction == "away"]
    h, a = score_at(events, sub_min)
    s = out.match.score
    reds = sum(1 for e in events if e.type == "card" and e.foul and e.foul.card in ("red", "second_yellow"))
    ok = bool(early and late and h > a and 1 <= s.home + s.away <= 4 and reds == 1)
    shots = [sum(1 for e in events if e.type == "shot" and e.team == side) for side in ("home", "away")]
    desc = (f"seed {seed}: candidates {[(c.minute, c.direction[0]) for c in cands]}, {h}-{a} at {sub_min}', "
            f"final {s.home}-{s.away}, shots {shots[0]}-{shots[1]}")
    return seed, ok, desc


def export(seed: int) -> None:
    out, events, metrics, cands = run(seed)
    calc = StatCalculator(out.match, events, out.frames_as_models())
    data = {
        "preset": {"name": DEMO_1021.name, "seed": seed, "plants": [p.model_dump(mode="json") for p in DEMO_1021.plants]},
        "match": out.match.model_dump(mode="json"),
        "events": [e.model_dump(mode="json") for e in events],
        "metrics": [m.model_dump(mode="json") for m in metrics],
        "candidates": [c.model_dump(mode="json") for c in cands],
        "player_stats": [p.model_dump(mode="json") for p in player_match_stats(calc)],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "demo-1021.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    frames = [f.model_dump(mode="json") for f in out.frames_as_models()]
    with gzip.open(OUT / "demo-1021.frames.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(frames, fh, separators=(",", ":"))
    s = out.match.score
    print(f"wrote eval/fixtures/demo-1021.json ({len(events)} events, {len(cands)} candidates, {s.home}-{s.away}) "
          f"and demo-1021.frames.json.gz ({len(frames)} frames)")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", type=int, default=0, help="number of seeds to try")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--seed", type=int, default=None, help="export this seed")
    args = ap.parse_args()
    if args.search:
        with ProcessPoolExecutor() as pool:
            for seed, ok, desc in pool.map(check, range(args.start, args.start + args.search)):
                if ok:
                    print("MATCH", desc, flush=True)
    if args.seed is not None:
        export(args.seed)


if __name__ == "__main__":
    main()
