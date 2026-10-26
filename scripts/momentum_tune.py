#!/usr/bin/env python3
"""Choose the momentum settings (cap, half-life, which actions) and then the alarm settings from
data, on matches cached by scripts/momentum_cache.py.

  uv run scripts/momentum_tune.py momentum --cache .pivot-data/momentum-cache.pkl
  uv run scripts/momentum_tune.py alarm --cache .pivot-data/momentum-cache.pkl
"""
from __future__ import annotations

import argparse
import itertools
import math
import pickle
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np

from pivot_core.analytics import detect_candidates, momentum_series
from pivot_core.analytics.changepoint import DetectorParams
from pivot_core.domain import MinuteMetric
from pivot_core.domain.common import attacking_view
from pivot_core.sim.engine import threat_value

DEMO_SEED = 29
BASE_TYPES = ("pass", "carry", "dribble", "shot")
EXTRA_TYPES = ("ball_recovery", "interception", "tackle")


def action_value(e) -> float:
    """Uncapped: the best of where the action starts and, if it worked, where it ends."""
    pts = [e.location]
    if e.type != "shot" and e.outcome == "success" and e.end_location is not None:
        pts.append(e.end_location)
    return max(threat_value(np.array(attacking_view(tuple(p), e.team))) for p in pts if p is not None)


def prepare(events):
    """Per minute: period, list of (side, value, type); plus the 5-minute xG gaps."""
    period_of: dict[int, int] = {}
    acts = defaultdict(list)
    for e in events:
        if e.period == 5:
            continue
        period_of.setdefault(e.minute, e.period)
        if e.location is not None and e.type in BASE_TYPES + EXTRA_TYPES:
            acts[e.minute].append((0 if e.team == "home" else 1, action_value(e), e.type))
    n = max(period_of) + 1
    xg = np.zeros(n)
    for e in events:
        if e.type == "shot" and e.period != 5:
            xg[e.minute] += (e.xg or 0) * (1 if e.team == "home" else -1)
    centred = np.convolve(xg, np.ones(5) / 5, mode="same")
    ahead = np.array([xg[t + 1:t + 6].sum() for t in range(n)])
    periods = []
    last = None
    for m in range(n):
        last = period_of.get(m, last)
        periods.append(last)
    goals = [(e.minute, 1 if e.team == "home" else -1) for e in events
             if e.type == "shot" and e.shot_outcome == "goal" and e.period != 5]
    return dict(n=n, periods=periods, acts=acts, xg_centred=centred, xg_ahead=ahead, goals=goals)


def series(p, cap, half_life, types, scale=None, agg="max"):
    decay = 0.5 ** (1 / half_life)
    scale = 1 / cap if scale is None else scale
    out, wh, wa, last = [], 0.0, 0.0, None
    for m in range(p["n"]):
        if p["periods"][m] != last:
            wh = wa = 0.0
            last = p["periods"][m]
        peak = [0.0, 0.0]
        for side, v, t in p["acts"].get(m, ()):
            if t in types:
                v = min(v, cap)
                peak[side] = max(peak[side], v) if agg == "max" else peak[side] + v
        wh = decay * wh + (1 - decay) * peak[0]
        wa = decay * wa + (1 - decay) * peak[1]
        out.append(max(-1.0, min(1.0, scale * (wh - wa))))
    return np.array(out)


def old_series(events):
    """ADR-0010 before B06-opta: tanh(30 * EWMA(xT added home - away)), half-life 5, reset per period."""
    threat = defaultdict(lambda: [0.0, 0.0])
    period_of = {}
    for e in events:
        if e.period == 5:
            continue
        period_of.setdefault(e.minute, e.period)
        threat[e.minute][0 if e.team == "home" else 1] += e.threat
    decay = 0.5 ** (1 / 5.0)
    out, ewma, last = [], 0.0, None
    for m in range(max(period_of) + 1):
        p = period_of.get(m, last)
        if p != last:
            ewma, last = 0.0, p
        th, ta = threat[m]
        ewma = decay * ewma + (1 - decay) * (th - ta)
        out.append(math.tanh(30 * ewma))
    return np.array(out)


def old_metrics(match_id, events):
    return [MinuteMetric(match_id=match_id, minute=m, momentum=round(float(v), 4), threat_home=0, threat_away=0,
                         pressure_home=0, pressure_away=0) for m, v in enumerate(old_series(events))]


def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0


def load(path):
    return pickle.loads(Path(path).read_bytes())


def lean_before_goals(p, m):
    """Scorer-side mean momentum over the 5 minutes before each goal, in units of the curve's spread."""
    sd = m.std() or 1.0
    return [s * m[g - 5:g].mean() / sd for g, s in p["goals"] if g >= 5]


def momentum_cmd(args):
    data = load(args.cache)
    if args.sb:
        from momentum_real import load_real
        data = [(n, mid, ev) for n, (mid, ev) in enumerate(load_real(Path(args.sb)), start=100_000)]
    prep = [(seed, prepare(ev)) for seed, _, ev in data if seed != DEMO_SEED]
    # value distribution of team-minute peaks: where does a cap bite?
    peaks = []
    for _, p in prep:
        for m in range(p["n"]):
            best = [0.0, 0.0]
            for side, v, t in p["acts"].get(m, ()):
                if t in BASE_TYPES:
                    best[side] = max(best[side], v)
            peaks += best
    peaks = np.array(peaks)
    print("team-minute peak value percentiles 50/75/90/95/99:",
          np.round(np.percentile(peaks, [50, 75, 90, 95, 99]), 3))
    old, old_lean = [], []
    for seed, mid, ev in data:
        if seed == DEMO_SEED:
            continue
        p = dict(prep)[seed]
        m = old_series(ev)
        old.append((corr(m, p["xg_centred"][:len(m)]), corr(m, p["xg_ahead"][:len(m)]), m.std(),
                    np.abs(np.diff(m)).mean()))
        old_lean += lean_before_goals(p, m)
    o = np.mean(old, axis=0)
    print(f"old (ADR-0010 xT-change EWMA): corr centred {o[0]:+.3f}, ahead {o[1]:+.3f}, sd {o[2]:.2f}, "
          f"mean |step| {o[3]:.3f}, lean before goals {np.mean(old_lean):+.2f} sd")
    rows = []
    for cap, hl, types, agg in itertools.product((0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 1.0),
                                                 (1.0, 1.5, 2.0, 3.0, 5.0),
                                                 (BASE_TYPES, BASE_TYPES + EXTRA_TYPES), ("max", "sum")):
        if agg == "sum" and (cap not in (0.1, 1.0) or types != BASE_TYPES):
            continue
        r, lean = [], []
        for _, p in prep:
            m = series(p, cap, hl, types, scale=1 / cap if agg == "max" else 1 / (cap * 8), agg=agg)
            r.append((corr(m, p["xg_centred"]), corr(m, p["xg_ahead"]), m.std(), np.abs(np.diff(m)).mean(),
                      float(np.mean(np.abs(m) >= 0.999))))
            lean += lean_before_goals(p, m)
        r = np.mean(r, axis=0)
        rows.append((cap, hl, "+def" if len(types) > 4 else "on-ball", agg, *r, np.mean(lean)))
    for cap in (0.1, 0.15, 0.2):
        raw = np.concatenate([series(p, cap, 1.5, BASE_TYPES, scale=1.0) for _, p in prep])
        q = np.percentile(np.abs(raw), [50, 90, 95, 99, 99.9])
        print(f"cap {cap}, half-life 1.5: |home - away| percentiles 50/90/95/99/99.9 {np.round(q, 4)}; "
              f"x(1/cap): {np.round(q / cap, 2)}")
    rows.sort(key=lambda x: -x[4])
    print("cap   half-life actions  agg  corr-centred corr-ahead  sd   |step| clipped lean-before-goals(sd)")
    for row in rows:
        print(f"{row[0]:<5} {row[1]:<9} {row[2]:<8} {row[3]:<4} {row[4]:+.3f}       {row[5]:+.3f}     "
              f"{row[6]:.2f} {row[7]:.3f}  {row[8]:.3f}   {row[9]:+.2f}")


# ---------------------------------------------------------------- alarm

def plant_minutes(events):
    red = next((e.minute for e in events if e.type == "card" and e.foul and e.foul.card in ("red", "second_yellow")
                and e.team == "away" and 35 <= e.minute <= 40), None)
    sub = next((e for e in events if e.type == "substitution" and e.substitution and e.substitution.reason == "tactical"
                and e.team == "home"), None)
    return red, (sub.minute if sub else None)


_DATA: dict = {}


def _init(path):
    _DATA.update(pickle.loads(Path(path).read_bytes()))


def evaluate(params, which="tune"):
    metrics_by_seed, events_by_seed = _DATA[which], _DATA["events"]
    rows = []
    for seed, (mid, ms) in metrics_by_seed.items():
        ev = events_by_seed[seed]
        cands = detect_candidates(mid, ms, ev, params)
        red, sub = plant_minutes(ev)
        goals = [e.minute for e in ev if e.type == "shot" and e.shot_outcome == "goal" and e.period != 5]
        rows.append(dict(
            seed=seed, n=len(cands), key=sum(bool(c.key_event_ids) for c in cands),
            red=any(c.direction == "home" and red is not None and red - 2 <= c.minute <= red + 6 for c in cands),
            sub=any(c.direction == "away" and sub is not None and sub - 1 <= c.minute <= sub + 7 for c in cands),
            goals=len(goals),
            goal_hit=sum(any(-2 <= c.minute - g <= 8 for c in cands) for g in goals),
            cands=[(c.minute, c.direction[0], round(c.swing, 2)) for c in cands]))
    return params, rows


def summary(rows):
    n = np.array([r["n"] for r in rows])
    total = max(n.sum(), 1)
    return dict(per_match=n.mean(), one_to_three=float(np.mean((n >= 1) & (n <= 3))),
                zero=float(np.mean(n == 0)), key=sum(r["key"] for r in rows) / total,
                red=float(np.mean([r["red"] for r in rows])), sub=float(np.mean([r["sub"] for r in rows])),
                goal_hit=sum(r["goal_hit"] for r in rows) / max(sum(r["goals"] for r in rows), 1))


def alarm_cmd(args):
    data = load(args.cache)
    if args.sb:
        from momentum_real import load_real
        data = [(n, mid, ev) for n, (mid, ev) in enumerate(load_real(Path(args.sb)), start=100_000)] +             [x for x in data if x[0] == DEMO_SEED]
    series_of = old_metrics if args.old else momentum_series
    work = Path(args.cache).with_suffix((".real" if args.sb else "") + (".old.pkl" if args.old else ".alarm.pkl"))
    work.write_bytes(pickle.dumps(dict(
        tune={seed: (mid, series_of(mid, ev)) for seed, mid, ev in data if seed != DEMO_SEED},
        demo={seed: (mid, series_of(mid, ev)) for seed, mid, ev in data if seed == DEMO_SEED},
        events={seed: ev for seed, _, ev in data})))
    _init(work)
    base = DetectorParams()
    print("current params:", base)
    grid = []
    for k, h, swing, gap in itertools.product(args.k, args.h, args.swing, args.gap):
        grid.append(replace(base, k=k, h=h, min_swing=swing, min_gap_min=gap))
    with ProcessPoolExecutor(initializer=_init, initargs=(str(work),)) as pool:
        res = list(pool.map(evaluate, grid, chunksize=4))
    out = []
    for params, rows in res:
        s = summary(rows)
        _, drows = evaluate(params, "demo")
        out.append((params, s, drows[0]["cands"] if drows else []))
    # targets (B09): 2-3 per match, almost every match 1-3; then most with a key event and the plants found
    ok = [x for x in out if args.lo <= x[1]["per_match"] <= args.hi and x[1]["one_to_three"] >= 0.75]
    ok.sort(key=lambda x: -(x[1]["key"] + 0.5 * (x[1]["red"] + x[1]["sub"]) + 0.5 * x[1]["one_to_three"]))
    print(f"{len(ok)} of {len(out)} settings meet 2-3 per match and >=75% of matches with 1-3")
    shown = out if args.all else (ok or sorted(out, key=lambda x: abs(x[1]["per_match"] - 2.5)))[:args.top]
    for params, s, dc in shown:
        print(f"k={params.k} h={params.h} swing={params.min_swing} gap={params.min_gap_min}: "
              f"{s['per_match']:.2f}/match, 1-3 {s['one_to_three']:.0%}, none {s['zero']:.0%}, key {s['key']:.0%}, "
              f"red found {s['red']:.0%}, sub found {s['sub']:.0%}, goals hit {s['goal_hit']:.0%} | demo {dc}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("momentum", "alarm"))
    ap.add_argument("--cache", default=".pivot-data/momentum-cache.pkl")
    ap.add_argument("--sb", default=None, help="StatsBomb folder: run `momentum` on real matches instead")
    ap.add_argument("--k", type=float, nargs="+", default=[0.02, 0.03, 0.04, 0.05, 0.06])
    ap.add_argument("--h", type=float, nargs="+", default=[0.3, 0.4, 0.5, 0.6, 0.8, 1.0])
    ap.add_argument("--swing", type=float, nargs="+", default=[0.08, 0.1, 0.12, 0.15, 0.2])
    ap.add_argument("--gap", type=int, nargs="+", default=[12])
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--lo", type=float, default=2.0, help="fewest candidates per match accepted")
    ap.add_argument("--hi", type=float, default=3.0)
    ap.add_argument("--all", action="store_true", help="print every setting in grid order (no ranking)")
    ap.add_argument("--old", action="store_true", help="the momentum before B06-opta, for before/after numbers")
    args = ap.parse_args()
    {"momentum": momentum_cmd, "alarm": alarm_cmd}[args.cmd](args)


if __name__ == "__main__":
    main()
