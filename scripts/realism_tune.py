#!/usr/bin/env python3
"""Search the simulator's parameters against the realism scorecard instead of turning one knob
at a time (B12).

  uv run scripts/realism_tune.py --rounds 12 --batch 6 --matches 60 --out .pivot-data/tune.json

Every candidate plays the same seeds (common random numbers), so two candidates differ by their
parameters, not by luck. Each round tries a batch of changes to the best set so far: most are
aimed (for the worst misses, turn the knob known to move that number in the direction that closes
the gap, KNOBS), the rest are random (a few parameters multiplied by a random factor). All stay
inside their bounds; the best candidate of the round replaces the incumbent if its loss is lower. The loss is scripts/realism_scorecard.py's: squared
misses in tolerance units against StatsBomb 2022 World Cup numbers and the literature ranges.
Finish by re-scoring the winner on fresh seeds before copying it into Params.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import realism_scorecard as sc  # noqa: E402

from pivot_core.sim.engine import Params  # noqa: E402

# name: (low, high)
SPACE = {
    # shots and goals
    "shot_xg_weight": (0.4, 2.5),
    "shot_min_xg": (0.01, 0.06),
    "long_shot_rate": (0.002, 0.03),
    "block_base": (0.1, 0.35),
    "loose_shot": (0.05, 0.8),
    "skill_gk": (0.5, 2.5),
    # duels, fouls and cards
    "tackle_attempt": (0.05, 0.35),
    "foul_rate": (0.25, 0.8),
    "yellow_rate": (0.06, 0.25),
    "red_rate": (0.001, 0.006),
    # passing
    "lane_cut": (0.08, 0.3),
    "intercept_share": (0.15, 0.7),
    "high_pass_acc": (0.55, 0.95),
    "pass_forward": (0.02, 0.08),
    "pass_threat": (6.0, 18.0),
    "skill_pass": (0.2, 1.2),
    # clearances, set pieces, offside, keepers
    "clear_under_pressure": (0.05, 0.7),
    "clear_behind": (0.1, 0.6),
    "aerial_contest": (1.5, 5.0),
    "offside_pen": (1.0, 4.5),
    "offside_slack": (0.2, 2.5),
    "claim_rate": (0.15, 1.0),
    "sweep_rate": (0.15, 1.0),
    # game state, fatigue, injuries
    "state_line": (0.5, 4.0),
    "state_shot": (0.0, 0.4),
    "waste_s": (2.0, 20.0),
    "fatigue_err": (0.05, 0.6),
    "injury_foul": (0.04, 0.3),
    "injury_sprint": (0.0001, 0.001),
    "line_lift": (0.0, 6.0),
    "var_disallow": (0.02, 0.08),
    "var_pen_award": (0.01, 0.08),
    "through_lead": (0.1, 1.0),
}

# Weights on the scorecard's loss terms: what the demo and the AI explanations lean on most.
WEIGHTS = {"goals": 3, "shots": 2, "xg_per_shot": 3, "corners": 2, "offsides": 2, "pass_accuracy_pct": 2,
           "loose_first_time_shot_pct": 2, "pass_high_pct": 2, "pass_low_pct": 2, "tackles_won_per_team": 2,
           "late_pass_acc_drop_pts": 2, "leader_shot_share": 2, "results_pct": 2, "red_cards": 3, "yellow_cards": 2,
           "pressures": 0.5, "counters": 0, "interceptions": 1, "ball_recoveries": 0.5, "clearances": 1,
           "final_third_passes": 1, "injuries": 0.5, "injury_subs": 0.5, "var_overturns": 0.5,
           "def_action_height_m": 2, "ppda": 2, "first_half_goals_pct": 1, "var_goals_disallowed": 1}


# Which knobs move which number, and which way (+1: a larger knob gives a larger number). Used to
# aim half of each round's candidates at the worst misses instead of at random parameters.
KNOBS = {
    "goals": [("shot_xg_weight", 1), ("skill_gk", -1)],
    "shots": [("shot_xg_weight", 1), ("long_shot_rate", 1), ("through_lead", 1), ("shot_min_xg", -1)],
    "xg_per_shot": [("long_shot_rate", -1), ("shot_min_xg", 1), ("block_base", -1)],
    "fouls": [("foul_rate", 1)],
    "yellow_cards": [("yellow_rate", 1)],
    "red_cards": [("yellow_rate", 1), ("red_rate", 1), ("foul_rate", 1)],
    "corners": [("clear_behind", 1)],
    "offsides": [("offside_slack", 1), ("offside_pen", -1)],
    "pass_accuracy_pct": [("lane_cut", -1), ("high_pass_acc", 1), ("skill_pass", 1)],
    "final_third_passes": [("pass_forward", 1), ("pass_threat", 1)],
    "tackles_won_per_team": [("tackle_attempt", 1)],
    "interceptions": [("intercept_share", 1), ("lane_cut", 1)],
    "ball_recoveries": [("intercept_share", -1)],
    "clearances": [("clear_under_pressure", 1), ("aerial_contest", 1)],
    "loose_first_time_shot_pct": [("loose_shot", 1)],
    "keeper_sweeps": [("sweep_rate", 1)],
    "keeper_claims": [("claim_rate", 1)],
    "late_pass_acc_drop_pts": [("fatigue_err", 1)],
    "leader_shot_share": [("state_line", -1), ("state_shot", -1)],
    "injuries": [("injury_foul", 1), ("injury_sprint", 1)],
    "injury_subs": [("injury_foul", 1), ("injury_sprint", 1)],
    "def_action_height_m": [("line_lift", 1)],
    "ppda": [("tackle_attempt", -1), ("foul_rate", -1)],
    "crosses": [("pass_threat", 1)],
    "var_goals_disallowed": [("var_disallow", 1)],
    "var_overturns": [("var_pen_award", 1)],
}


def misses(agg: dict, ref: dict) -> list[tuple[float, str, float]]:
    """(weighted loss, metric, signed miss) per metric, worst first."""
    out = []
    for key, _, _ in sc.CARD:
        if key not in KNOBS or agg.get(key) is None:
            continue
        only = {k: (WEIGHTS.get(k, 1.0) if k == key else 0) for k, _, _ in sc.CARD} | {"results_pct": 0}
        real, _ = sc.real_value(ref, key)
        if real is None:
            continue
        mid = sum(real) / 2 if isinstance(real, tuple) else real
        out.append((sc.loss({key: agg[key]}, ref, only), key, agg[key] - mid))
    return sorted(out, reverse=True)


def aim(best: dict, agg: dict, ref: dict, rng: np.random.Generator, n: int, step: float) -> list[dict]:
    """Candidates that each turn one knob of one of the worst metrics the way that closes the gap."""
    cands = []
    for _, key, miss in misses(agg, ref):
        for name, sign in KNOBS[key]:
            if name not in best or len(cands) >= n:
                continue
            lo, hi = SPACE[name]
            factor = np.exp(-np.sign(miss) * sign * step * rng.uniform(0.6, 1.4))
            cand = dict(best)
            cand[name] = float(np.clip(best[name] * factor, lo, hi))
            if cand[name] != best[name]:
                cands.append(cand)
    return cands


def evaluate(overrides: dict, seeds: range, ref: dict, pool: ProcessPoolExecutor, scenario: str) -> tuple[float, dict]:
    agg = sc.aggregate(sc.run_sim(scenario, seeds, overrides, None, pool))
    return sc.loss(agg, ref, WEIGHTS), agg


def propose(best: dict, rng: np.random.Generator, n_change: int, sigma: float) -> dict:
    cand = dict(best)
    for name in rng.choice(sorted(best), size=n_change, replace=False):
        lo, hi = SPACE[name]
        cand[name] = float(np.clip(cand[name] * np.exp(rng.normal(0, sigma)), lo, hi))
    return cand


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--batch", type=int, default=6)
    ap.add_argument("--matches", type=int, default=60)
    ap.add_argument("--seed", type=int, default=5000)
    ap.add_argument("--scenario", default="mirror")
    ap.add_argument("--sigma", type=float, default=0.25)
    ap.add_argument("--change", type=int, default=3, help="parameters changed per candidate")
    ap.add_argument("--start", type=Path, help="JSON of a previous run to continue from")
    ap.add_argument("--out", type=Path, default=Path(".pivot-data/realism_tune.json"))
    args = ap.parse_args()

    ref = json.loads(sc.REFERENCE.read_text(encoding="utf-8"))
    defaults = asdict(Params())
    best = {name: float(defaults[name]) for name in SPACE if name in defaults}
    if args.start:
        best.update(json.loads(args.start.read_text(encoding="utf-8"))["best"])
    seeds = range(args.seed, args.seed + args.matches)
    rng = np.random.default_rng(args.seed)
    log = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor() as pool:
        best_loss, best_agg = evaluate(best, seeds, ref, pool, args.scenario)
        print(f"start loss {best_loss:.1f}")
        for rnd in range(args.rounds):
            aimed = aim(best, best_agg, ref, rng, args.batch - args.batch // 3, 2 * args.sigma)
            cands = aimed + [propose(best, rng, args.change, args.sigma) for _ in range(args.batch - len(aimed))]
            scored = [(evaluate(c, seeds, ref, pool, args.scenario), c) for c in cands]
            (loss, agg), cand = min(scored, key=lambda s: s[0][0])
            log.append({"round": rnd, "losses": [s[0][0] for s in scored], "best_loss": min(loss, best_loss)})
            if loss < best_loss:
                changed = {k: round(v, 4) for k, v in cand.items() if v != best[k]}
                best, best_loss, best_agg = cand, loss, agg
                print(f"round {rnd}: loss {loss:.1f}  {changed}")
            else:
                print(f"round {rnd}: no better ({loss:.1f})")
            args.out.write_text(json.dumps({"best": best, "loss": best_loss, "log": log,
                                            "card": {k: v for k, v in best_agg.items() if not isinstance(v, list)}},
                                           indent=2), encoding="utf-8")
    sc.print_card(f"best after {args.rounds} rounds", best_agg, ref)
    print(json.dumps({k: round(v, 4) for k, v in best.items()}, indent=2))


if __name__ == "__main__":
    main()
