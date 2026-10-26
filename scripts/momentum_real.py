#!/usr/bin/env python3
"""Momentum and the alarm on real matches (StatsBomb open data, 2022 World Cup) next to simulated
ones, both through the very same code (MET-024, B06).

  uv run scripts/momentum_real.py --sb <folder with matches.json and events/> --cache .pivot-data/momentum-cache.pkl

The StatsBomb files are read only and never committed. Real events are turned into our event
format: StatsBomb coordinates (120 x 80, the acting team attacking left to right) are scaled to
105 x 68 and put on the home side's frame, so `attacking_view` turns them back; passes, carries,
dribbles and shots keep their start, successful end and outcome; `threat` is the threat surface's
gain on a successful pass or carry (as the simulator records it), for the old momentum. Goals
(own goals left out), red cards and substitutions are kept for the alarm's key events. Elapsed
minutes run on through stoppage time, as in the simulator.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from dataclasses import fields
from pathlib import Path

import numpy as np

from pivot_core.analytics import DetectorParams, detect_candidates, momentum_series
from pivot_core.domain import FoulDetail, MatchEvent
from pivot_core.domain.common import PITCH_LENGTH, PITCH_WIDTH, attacking_view
from pivot_core.sim.engine import threat_value

sys.path.insert(0, str(Path(__file__).resolve().parent))
from momentum_tune import DEMO_SEED, old_metrics  # noqa: E402

PERIOD_START = {1: 0, 2: 45 * 60, 3: 90 * 60, 4: 105 * 60}
TYPES = {"Pass": "pass", "Carry": "carry", "Dribble": "dribble", "Shot": "shot"}


def _xy(loc, own_side_view: bool):
    x, y = loc[0] * PITCH_LENGTH / 120, loc[1] * PITCH_WIDTH / 80
    x, y = min(max(x, 0.0), PITCH_LENGTH), min(max(y, 0.0), PITCH_WIDTH)
    return (x, y) if own_side_view else (PITCH_LENGTH - x, PITCH_WIDTH - y)


def real_match(match: dict, raw: list[dict]) -> tuple[str, list[MatchEvent]]:
    mid = f"WC22-{match['match_id']}"
    home = match["home_team"]["home_team_name"]
    clock = {}
    for e in raw:
        p = e["period"]
        if p in PERIOD_START:
            clock[p] = max(clock.get(p, 0), e["minute"] * 60 + e["second"] - PERIOD_START[p])
    offset, acc = {}, 0
    for p in sorted(clock):
        offset[p] = acc
        acc += clock[p] + 1
    out = []
    for e in raw:
        p, name = e["period"], e["type"]["name"]
        if p not in offset:
            continue
        side = "home" if e["team"]["name"] == home else "away"
        period_t = max(0, min(3600, e["minute"] * 60 + e["second"] - PERIOD_START[p]))
        base = dict(match_id=mid, seq=len(out), event_id=f"e{len(out)}", t=offset[p] + period_t, period=p,
                    period_t=period_t, team=side)
        if name in TYPES:
            kind = TYPES[name]
            detail = e.get(name.lower(), {})
            loc = _xy(e["location"], side == "home") if e.get("location") else None
            end, outcome, shot_outcome = None, None, None
            if kind == "pass":
                outcome = "fail" if detail.get("outcome") else "success"
                end = _xy(detail["end_location"], side == "home") if detail.get("end_location") else None
            elif kind == "carry":
                outcome = "success"
                end = _xy(detail["end_location"], side == "home") if detail.get("end_location") else None
            elif kind == "dribble":
                outcome = "success" if detail.get("outcome", {}).get("name") == "Complete" else "fail"
            else:
                shot_outcome = "goal" if detail.get("outcome", {}).get("name") == "Goal" else "saved"
            threat = 0.0
            if outcome == "success" and loc and end:
                threat = threat_value(attacking_view(end, side)) - threat_value(attacking_view(loc, side))
            out.append(MatchEvent(**base, type=kind, location=loc, end_location=end, outcome=outcome,
                                  shot_outcome=shot_outcome, xg=detail.get("statsbomb_xg"), threat=round(threat, 4)))
        elif name == "Substitution":
            out.append(MatchEvent(**base, type="substitution"))
        elif name in ("Foul Committed", "Bad Behaviour"):
            card = (e.get("foul_committed") or e.get("bad_behaviour") or {}).get("card", {}).get("name")
            if card in ("Red Card", "Second Yellow"):
                out.append(MatchEvent(**base, type="card", foul=FoulDetail(
                    foul_type="tackle", card="red" if card == "Red Card" else "second_yellow")))
    out.sort(key=lambda e: (e.t, e.seq))
    return mid, out


def load_real(folder: Path):
    matches = json.loads((folder / "matches.json").read_text(encoding="utf-8"))
    for m in sorted(matches, key=lambda m: m["match_id"]):
        raw = json.loads((folder / "events" / f"{m['match_id']}.json").read_text(encoding="utf-8"))
        yield real_match(m, raw)


def describe(mid, events, metrics, params):
    m = np.array([x.momentum for x in metrics])
    # who is on top, with a little hysteresis so a curve sitting on 0 does not count as changing sides
    side, changes = 0, 0
    for v in m:
        s = 1 if v > 0.1 else -1 if v < -0.1 else 0
        if s and side and s != side:
            changes += 1
        side = s or side
    swings = [abs(m[t:t + 5].mean() - m[t - 5:t].mean()) for t in range(5, len(m) - 5)]
    lean = []
    for e in events:
        if e.type == "shot" and e.shot_outcome == "goal" and e.minute >= 5:
            sign = 1 if e.team == "home" else -1
            lean.append(sign * m[e.minute - 5:e.minute].mean())
    cands = detect_candidates(mid, metrics, events, params)
    return dict(changes=changes, strong=float(np.mean(np.abs(m) >= 0.3)), swing90=float(np.percentile(swings, 90)),
                lean=lean, n=len(cands), key=sum(bool(c.key_event_ids) for c in cands))


def table(rows):
    lean = np.concatenate([r["lean"] for r in rows]) if rows else np.array([])
    n = np.array([r["n"] for r in rows])
    return dict(matches=len(rows), changes=np.mean([r["changes"] for r in rows]),
                strong=np.mean([r["strong"] for r in rows]), swing90=np.mean([r["swing90"] for r in rows]),
                lean=float(lean.mean()), lean_pos=float(np.mean(lean > 0)), goals=len(lean),
                per_match=n.mean(), one_to_three=float(np.mean((n >= 1) & (n <= 3))), zero=float(np.mean(n == 0)),
                key=sum(r["key"] for r in rows) / max(n.sum(), 1))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sb", required=True)
    ap.add_argument("--cache", default=".pivot-data/momentum-cache.pkl")
    for f in fields(DetectorParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=None)
    args = ap.parse_args()
    params = DetectorParams(**{f.name: getattr(args, f.name) for f in fields(DetectorParams)
                               if getattr(args, f.name) is not None})
    old_params = DetectorParams(k=0.1, h=1.5, min_swing=0.3, min_gap_min=12)
    print("alarm params:", params)
    real = list(load_real(Path(args.sb)))
    sim = [(mid, ev) for seed, mid, ev in pickle.loads(Path(args.cache).read_bytes()) if seed != DEMO_SEED]
    res = {}
    for label, matches in (("real WC2022", real), ("simulated", sim)):
        res[label, "new"] = table([describe(mid, ev, momentum_series(mid, ev), params) for mid, ev in matches])
        res[label, "old"] = table([describe(mid, ev, old_metrics(mid, ev), old_params) for mid, ev in matches])
    print("| | matches | side changes / match | minutes with |m| >= 0.3 | 90th pct 5-min swing | "
          "scorer-side momentum, 5 min before a goal (share > 0) | pivots / match | 1-3 pivots | none | "
          "pivots next to goal / red / sub |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for (label, which), t in res.items():
        print(f"| {label}, {which} | {t['matches']} | {t['changes']:.1f} | {t['strong']:.0%} | {t['swing90']:.2f} | "
              f"{t['lean']:+.2f} ({t['lean_pos']:.0%} of {t['goals']}) | {t['per_match']:.2f} | "
              f"{t['one_to_three']:.0%} | {t['zero']:.0%} | {t['key']:.0%} |")


if __name__ == "__main__":
    main()
