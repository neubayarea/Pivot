#!/usr/bin/env python3
"""What the off-pitch context effects (B14) do to a match: the demo with the switch off and on, and
paired seeds side by side.

  uv run scripts/effects_report.py                 # the demo match, then 60 paired seeds
  uv run scripts/effects_report.py --pairs 200

The demo is played with its season stories filled in before kick-off (careers, form, news,
relationships), so the effects it gets are the ones in eval/fixtures/demo-1021.json. The paired
seeds use plain generated matches: their effects come from the crowd, the competition and each
player's personality only. Nothing is written; the demo files never change here.
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from pivot_core.analytics import detect_candidates, momentum_series
from pivot_core.sim import DEMO_1021, build_demo_match, simulate
from pivot_core.sim.season import load_season, with_season

FIXTURES = Path(__file__).resolve().parents[1] / "eval" / "fixtures"


def describe(out) -> str:
    events = out.events_as_models()
    cands = detect_candidates(out.match.match_id, momentum_series(out.match.match_id, events), events)
    cards = [f"{e.clock_label} {e.player_id} {e.foul.card}" for e in events if e.type == "card"]
    goals = [f"{e.clock_label} {e.team}" for e in events if e.type == "shot" and e.shot_outcome == "goal"]
    s = out.match.score
    return (f"{s.home}-{s.away}  alarms {[f'{c.minute} {c.direction}' for c in cands]}\n"
            f"      goals {goals}\n      cards {cards}")


def counts(job: tuple[int, bool]) -> dict:
    seed, on = job
    out = simulate(build_demo_match(seed), context_effects=on)
    ev = out.events
    s = out.match.score
    return {"home": s.home > s.away, "draw": s.home == s.away, "away": s.home < s.away, "goals": s.home + s.away,
            "fouls": sum(e["type"] == "foul" for e in ev), "cards": sum(e["type"] == "card" for e in ev),
            "reds": sum(e["type"] == "card" and e["foul"]["card"] in ("red", "second_yellow") for e in ev),
            "injuries": sum(e["type"] == "injury" for e in ev),
            "effects": len(out.match.context.effects)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=60)
    ap.add_argument("--seed", type=int, default=5000)
    args = ap.parse_args()

    demo = with_season(DEMO_1021.build(), load_season(FIXTURES))
    plants = list(DEMO_1021.plants)
    for on in (False, True):
        out = simulate(demo, plants=plants, context_effects=on)
        print(f"demo seed {DEMO_1021.seed}, effects {'on ' if on else 'off'}: {describe(out)}")

    if args.pairs:
        seeds = range(args.seed, args.seed + args.pairs)
        with ProcessPoolExecutor() as pool:
            rows = {on: list(pool.map(counts, [(s, on) for s in seeds], chunksize=4)) for on in (False, True)}
        print(f"\n{args.pairs} paired seeds from {args.seed}, per match (off -> on):")
        for key in ("home", "draw", "away"):
            a, b = (100 * np.mean([r[key] for r in rows[on]]) for on in (False, True))
            print(f"  {key + ' win' if key != 'draw' else 'draw':9} {a:5.1f}% -> {b:5.1f}%")
        for key in ("goals", "fouls", "cards", "reds", "injuries", "effects"):
            a, b = (np.mean([r[key] for r in rows[on]]) for on in (False, True))
            print(f"  {key:9} {a:6.2f} -> {b:6.2f}")


if __name__ == "__main__":
    main()
