#!/usr/bin/env python3
"""How real does a simulated match look? The same numbers on N simulated matches and on real
football, side by side (B12).

  uv run scripts/realism_scorecard.py                       # 120 matches per scenario
  uv run scripts/realism_scorecard.py --matches 240 --red 120
  uv run scripts/realism_scorecard.py --build-reference <statsbomb dir>

Real numbers come from eval/realism/reference.json:

- "wc2022": counted with --build-reference from StatsBomb open data, 2022 World Cup (64
  matches; the raw files are never committed). Regular time only (periods 1 and 2).
- "literature": what event data cannot give (results, line height, VAR), with the source
  next to each number.

Besides averages the card compares conditional effects: goals by minute, the leading side's
share of shots and passes, the 11-man side after a red card, late-game pass accuracy, and the
leading side's back line late in the game against the first 20 minutes.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import fields
from pathlib import Path

import numpy as np

from pivot_core.domain import PlantSpec
from pivot_core.sim import build_demo_match
from pivot_core.sim.engine import Engine, Params

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "eval" / "realism" / "reference.json"
L, W = 105.0, 68.0
BINS = (15, 30, 45, 60, 75, 90)                   # goals by minute: 0-15, ..., 75-90+ (stoppage in the last bin)

# Who plays whom. "demo" is the demo pairing; "mirror" takes formation and strength away and
# leaves only home advantage; "swap" turns the demo formations round.
SCENARIOS = {
    "demo": dict(home_strength=72.0, away_strength=70.0, home_formation="4-3-3", away_formation="4-2-3-1"),
    "mirror": dict(home_strength=71.0, away_strength=71.0, home_formation="4-3-3", away_formation="4-3-3"),
    "swap": dict(home_strength=71.0, away_strength=71.0, home_formation="4-2-3-1", away_formation="4-3-3"),
    "gap": dict(home_strength=66.0, away_strength=76.0, home_formation="4-3-3", away_formation="4-3-3"),
}
RED = PlantSpec(minute=38, type="red_card", team="away")


# --- shared helpers -------------------------------------------------------------------

def _clock(period: int, period_t: float) -> float:
    """Scoreboard minute as a float; stoppage time stays in its half's last bin."""
    return min(period_t / 60, 44.999) + (45 if period == 2 else 0)


def _bin(minute: float) -> int:
    return next(n for n, hi in enumerate(BINS) if minute < hi)


class _Tally:
    """Counts one match's events from a single team-aware stream (sim or StatsBomb)."""

    def __init__(self) -> None:
        self.c: Counter = Counter()
        self.score = [0, 0]
        self.red_side: int | None = None
        self.goal_bins = [0] * len(BINS)

    def shot(self, k: int, goal: bool, minute: float) -> None:
        lead = self.score[k] - self.score[1 - k]
        if lead:
            self.c["lead_shots"] += 1
            self.c["lead_shots_leader"] += lead > 0
        if self.red_side is not None:
            self.c["red_shots"] += 1
            self.c["red_shots_11"] += k != self.red_side
        if goal:
            self.goal(k, minute)

    def goal(self, k: int, minute: float) -> None:
        self.score[k] += 1
        self.goal_bins[_bin(minute)] += 1

    def pass_(self, k: int, ok: bool, minute: float) -> None:
        late = minute >= 75
        self.c["late_passes" if late else "early_passes"] += 1
        self.c["late_ok" if late else "early_ok"] += ok
        lead = self.score[k] - self.score[1 - k]
        if lead:
            self.c["lead_passes"] += 1
            self.c["lead_passes_leader"] += lead > 0
        if self.red_side is not None:
            self.c["red_passes"] += 1
            self.c["red_passes_11"] += k != self.red_side

    def finish(self, row: dict) -> dict:
        c = self.c
        row["late_pass_acc_drop_pts"] = (100 * (c["early_ok"] / max(c["early_passes"], 1) - c["late_ok"] / max(c["late_passes"], 1))
                                         if c["late_passes"] > 50 else None)
        for key in ("lead_shots", "lead_shots_leader", "lead_passes", "lead_passes_leader",
                    "red_shots", "red_shots_11", "red_passes", "red_passes_11"):
            row["_" + key] = c[key]
        row["_goal_bins"] = self.goal_bins
        return row


# --- simulated matches ----------------------------------------------------------------

def _gk_slots(out, k: int) -> np.ndarray:
    team = out.match.home if k == 0 else out.match.away
    gk = {s.player_id for s in team.sheet.starters if s.role == "GK"}
    return np.array([[pid in gk for pid in ids[k]] for ids in out.frames_ids])


def sim_metrics(out) -> dict:
    ev = out.events
    by_id = {e["event_id"]: e for e in ev}
    side = {"home": 0, "away": 1}
    tally = _Tally()
    row: Counter = Counter()
    heights: Counter = Counter()
    xgs = []
    np_shots = loose_ft = headers = 0
    pens = pen_goals = 0
    for e in ev:
        typ, k = e["type"], side[e["team"]]
        if e["period"] > 2:
            continue
        minute = _clock(e["period"], e["period_t"])
        if typ == "shot":
            goal = e["shot_outcome"] == "goal"
            row["shots"] += 1
            row["shots_on_target"] += e["shot_outcome"] in ("goal", "saved")
            xgs.append(e["xg"])
            tally.shot(k, goal, minute)
            row["goals"] += goal
            spot = L - 11 if k == 0 else 11.0                # a penalty is the only shot from the spot itself
            if abs(e["location"][0] - spot) < 0.05 and abs(e["location"][1] - W / 2) < 0.05:
                pens += 1
                pen_goals += goal
                continue
            np_shots += 1
            headers += e.get("body_part") == "head"
            assisted = any(by_id.get(r, {}).get("type") == "pass" for r in e.get("related_event_ids", []))
            loose_ft += bool(e.get("first_time")) and not assisted
        elif typ == "pass":
            pt = e.get("pass_type")
            row["corners"] += pt == "corner"
            row["crosses"] += pt in ("cross", "corner") and e.get("pass_height") == "high"
            row["throw_ins"] += pt == "throw_in"
            row["goal_kicks"] += pt == "goal_kick"
            ok = e["outcome"] == "success"
            tally.pass_(k, ok, minute)
            if pt == "throw_in":
                continue
            row["passes"] += 1
            row["passes_ok"] += ok
            heights[e.get("pass_height")] += 1
            sx = e["location"][0] if k == 0 else L - e["location"][0]
            ex = e["end_location"][0] if k == 0 else L - e["end_location"][0]
            row["final_third_passes"] += ok and sx < 70 and ex >= 70
        elif typ == "offside":
            row["offsides"] += 1
        elif typ == "foul":
            row["fouls"] += 1
        elif typ == "card":
            card = e["foul"]["card"]
            row["yellow_cards"] += card == "yellow"
            row["red_cards"] += card in ("red", "second_yellow")
            if card in ("red", "second_yellow") and tally.red_side is None:
                tally.red_side = k
        elif typ == "tackle":
            row["tackles_won_per_team"] += (e["outcome"] == "success") / 2
        elif typ == "interception":
            row["interceptions"] += 1
        elif typ == "ball_recovery":
            row["ball_recoveries"] += 1
        elif typ == "clearance":
            row["clearances"] += 1
        elif typ == "pressure":
            row["pressures"] += 1
        elif typ == "goalkeeper":
            act = e.get("keeper_action")
            row["keeper_sweeps"] += act == "sweep"
            row["keeper_claims"] += act in ("claim", "punch")
        elif typ == "injury":
            row["injuries"] += 1
        elif typ == "substitution":
            row["injury_subs"] += e["substitution"]["reason"] == "injury"
        elif typ == "var_review":
            row["var_overturns"] += e["var"]["decision"] == "overturned"
    out_row = {key: float(row[key]) for key in (
        "goals", "shots", "shots_on_target", "corners", "offsides", "fouls", "yellow_cards", "red_cards",
        "passes", "final_third_passes", "tackles_won_per_team", "interceptions", "clearances", "pressures",
        "keeper_sweeps", "keeper_claims", "injuries", "injury_subs", "var_overturns", "crosses", "throw_ins",
        "goal_kicks", "ball_recoveries")}
    out_row["xg_per_shot"] = float(np.mean(xgs)) if xgs else None
    out_row["pass_accuracy_pct"] = 100 * row["passes_ok"] / max(row["passes"], 1)
    hsum = max(sum(heights.values()), 1)
    for h in ("ground", "low", "high"):
        out_row[f"pass_{h}_pct"] = 100 * heights[h] / hsum
    out_row["loose_first_time_shot_pct"] = 100 * loose_ft / np_shots if np_shots else None
    out_row["header_shot_pct"] = 100 * headers / np_shots if np_shots else None
    out_row["counters"] = float(len({e["possession_id"] for e in ev if e.get("play_pattern") == "counter"}))
    out_row["_pens"], out_row["_pen_goals"] = pens, pen_goals
    out_row.update(_frame_metrics(out))
    s = out.match.score
    out_row["_result"] = "H" if s.home > s.away else ("A" if s.away > s.home else "D")
    out_row["_decided_by"] = out.match.decided_by
    return tally.finish(out_row)


def _frame_metrics(out) -> dict:
    """Back-line height and keeper position from the tracking frames (team view, metres from
    the own goal line). Back line = mean of the four deepest outfield players. The late-game
    shifts compare the line while defending (the other side has the ball)."""
    live = out.frames_possession >= 0
    if not live.any():
        return {}
    goals = sorted((e["t"], 0 if e["team"] == "home" else 1) for e in out.events
                   if e["type"] == "shot" and e["shot_outcome"] == "goal")
    t = out.frames_t
    lead = np.zeros(len(t), dtype=int)                    # home minus away at each frame
    for gt, k in goals:
        lead[t > gt] += 1 if k == 0 else -1
    second = out.frames_period == 2
    start2 = t[np.argmax(second)] if second.any() else 0
    minute = np.where(second, 45 + np.minimum((t - start2) / 60, 44.999), np.minimum(t / 60, 44.999))
    res: dict = {}
    lines, def_lines, keeper, late_lead, late_trail = [], [], [], [], []
    for k in (0, 1):
        x = out.frames_pos[:, k, :, 0]
        xv = x if k == 0 else L - x
        gk = _gk_slots(out, k)
        active = np.array([[pid is not None for pid in ids[k]] for ids in out.frames_ids])
        field = np.where(active & ~gk, xv, np.inf)
        back = np.sort(field, axis=1)[:, :4]
        back = np.where(np.isfinite(back), back, np.nan)
        line = np.nanmean(back, axis=1)
        gx = np.where(gk & active, xv, np.nan)
        gx = np.nanmin(np.where(np.isnan(gx), np.inf, gx), axis=1)
        lines.append(line[live].mean())
        defending = out.frames_possession == 1 - k
        def_lines.append(line[defending].mean())
        keeper.append(gx[live & np.isfinite(gx)].mean())
        mine = lead if k == 0 else -lead
        e_mask = defending & (minute < 20)
        if e_mask.any():
            l_mask = defending & (minute >= 70) & (mine > 0)
            t_mask = defending & (minute >= 70) & (mine < 0)
            if l_mask.sum() > 120:
                late_lead.append(line[l_mask].mean() - line[e_mask].mean())
            if t_mask.sum() > 120:
                late_trail.append(line[t_mask].mean() - line[e_mask].mean())
    res["back_line_m"] = float(np.mean(lines))
    res["back_line_defending_m"] = float(np.mean(def_lines))
    res["keeper_x_m"] = float(np.nanmean(keeper))
    res["_lead_line_shift"] = late_lead
    res["_trail_line_shift"] = late_trail
    return res


def _run_one(job: tuple) -> dict:
    scenario, seed, overrides, plant = job
    m = build_demo_match(seed, **SCENARIOS[scenario])
    params = Params(**overrides) if overrides else None
    eng = Engine(m, seed, params, [RED] if plant else None)
    out = eng.run()
    row = sim_metrics(out)
    if plant is not None:
        row["_red_after"] = _after_red(out)
    return row


def _after_red(out) -> dict:
    """From 38' on: home (the 11-man side when the away red is planted) share of shots and of
    live-ball possession, and the result."""
    start = 37 * 60
    shots = [e for e in out.events if e["type"] == "shot" and e["period"] <= 2 and (e["period"] == 2 or e["period_t"] >= start)]
    t0 = next((e["t"] for e in out.events if e["period"] == 1 and e["period_t"] >= start), 0)
    poss = out.frames_possession[out.frames_t >= t0]
    live = poss >= 0
    goals_before = [0, 0]
    for e in out.events:
        if e["t"] >= t0:
            break
        if e["type"] == "shot" and e["shot_outcome"] == "goal":
            goals_before[0 if e["team"] == "home" else 1] += 1
    return {"home_shots": sum(e["team"] == "home" for e in shots), "shots": len(shots),
            "home_poss": float(np.mean(poss[live] == 0)) if live.any() else 0.5,
            "level_at_37": goals_before[0] == goals_before[1]}


def run_sim(scenario: str, seeds: range, overrides: dict | None = None, plant: bool | None = None,
            pool: ProcessPoolExecutor | None = None) -> list[dict]:
    jobs = [(scenario, s, overrides or {}, plant) for s in seeds]
    if pool is None:
        with ProcessPoolExecutor() as p:
            return list(p.map(_run_one, jobs, chunksize=2))
    return list(pool.map(_run_one, jobs, chunksize=2))


def aggregate(rows: list[dict]) -> dict:
    """Per-match means plus the pooled conditional numbers."""
    agg: dict = {}
    keys = [k for k in rows[0] if not k.startswith("_")]
    for key in keys:
        vals = [r[key] for r in rows if r.get(key) is not None]
        agg[key] = float(np.mean(vals)) if vals else None
    tot = Counter()
    for r in rows:
        for key, v in r.items():
            if key.startswith("_") and isinstance(v, (int, float)) and not isinstance(v, bool):
                tot[key] += v
    agg["leader_shot_share"] = tot["_lead_shots_leader"] / max(tot["_lead_shots"], 1)
    agg["leader_pass_share"] = tot["_lead_passes_leader"] / max(tot["_lead_passes"], 1)
    agg["red_11_shot_share"] = tot["_red_shots_11"] / tot["_red_shots"] if tot["_red_shots"] else None
    agg["red_11_pass_share"] = tot["_red_passes_11"] / tot["_red_passes"] if tot["_red_passes"] else None
    agg["red_matches"] = sum(1 for r in rows if r.get("_red_passes"))
    agg["penalty_conversion"] = tot["_pen_goals"] / tot["_pens"] if tot["_pens"] else None
    bins = np.sum([r["_goal_bins"] for r in rows], axis=0)
    agg["goal_minute_share"] = [float(b) for b in bins / max(bins.sum(), 1)]
    if "_result" in rows[0]:
        res = Counter(r["_result"] for r in rows)
        agg["results_pct"] = [100 * res[x] / len(rows) for x in "HDA"]
    for key in ("_lead_line_shift", "_trail_line_shift"):
        vals = [v for r in rows for v in r.get(key, [])]
        agg[key[1:]] = float(np.mean(vals)) if vals else None
    agg["matches"] = len(rows)
    return agg


# --- real matches (StatsBomb) ---------------------------------------------------------

def build_reference(sb_dir: Path) -> dict:
    """Count the same numbers on StatsBomb open data (regular time only)."""
    matches = json.loads((sb_dir / "matches.json").read_text(encoding="utf-8"))
    rows = []
    shootout = Counter()
    for m in matches:
        ev = json.loads((sb_dir / "events" / f"{m['match_id']}.json").read_text(encoding="utf-8"))
        home = m["home_team"]["home_team_name"]
        rows.append(_sb_match(ev, home, shootout))
    agg = aggregate(rows)
    agg.pop("results_pct", None)
    agg["shootout_conversion"] = shootout["goal"] / max(shootout["kicks"], 1)
    agg["shootout_kicks"] = shootout["kicks"]
    agg["extra_time_share_knockout"] = sum(1 for m in matches if m["competition_stage"]["name"] != "Group Stage"
                                           and m.get("home_score") == m.get("away_score")) / max(
        sum(1 for m in matches if m["competition_stage"]["name"] != "Group Stage"), 1)
    return agg


def _sb_match(ev: list[dict], home: str, shootout: Counter) -> dict:
    tally = _Tally()
    row: Counter = Counter()
    heights: Counter = Counter()
    xgs = []
    np_shots = loose_ft = headers = 0
    pens = pen_goals = 0
    counters = set()
    for e in ev:
        typ = e["type"]["name"]
        period = e["period"]
        team = e.get("team", {}).get("name")
        k = 0 if team == home else 1
        if period == 5 and typ == "Shot":
            shootout["kicks"] += 1
            shootout["goal"] += e["shot"]["outcome"]["name"] == "Goal"
        if period > 2:
            continue
        period_t = e["minute"] * 60 + e["second"] - (45 * 60 if period == 2 else 0)
        minute = _clock(period, period_t)
        if e.get("play_pattern", {}).get("name") == "From Counter" and team is not None:
            counters.add(e["possession"])
        if typ == "Shot":
            s = e["shot"]
            goal = s["outcome"]["name"] == "Goal"
            row["shots"] += 1
            row["shots_on_target"] += s["outcome"]["name"] in ("Goal", "Saved", "Saved To Post")
            xgs.append(s["statsbomb_xg"])
            tally.shot(k, goal, minute)
            row["goals"] += goal
            if s["type"]["name"] == "Penalty":
                pens += 1
                pen_goals += goal
                continue
            np_shots += 1
            headers += s["body_part"]["name"] == "Head"
            loose_ft += bool(s.get("first_time")) and "key_pass_id" not in s
        elif typ == "Own Goal For":
            tally.goal(k, minute)
            row["goals"] += 1
        elif typ == "Pass":
            p = e["pass"]
            ptype = p.get("type", {}).get("name")
            row["corners"] += ptype == "Corner"
            row["crosses"] += (bool(p.get("cross")) or ptype == "Corner") and p["height"]["name"] == "High Pass"
            row["throw_ins"] += ptype == "Throw-in"
            row["goal_kicks"] += ptype == "Goal Kick"
            if p.get("outcome", {}).get("name") == "Pass Offside":
                row["offsides"] += 1
            ok = "outcome" not in p
            tally.pass_(k, ok, minute)
            if ptype == "Throw-in":
                continue
            row["passes"] += 1
            row["passes_ok"] += ok
            heights[{"Ground Pass": "ground", "Low Pass": "low", "High Pass": "high"}[p["height"]["name"]]] += 1
            sx, ex = e["location"][0] * L / 120, p["end_location"][0] * L / 120
            row["final_third_passes"] += ok and sx < 70 and ex >= 70
        elif typ == "Offside":
            row["offsides"] += 1
        elif typ == "Foul Committed":
            row["fouls"] += 1
            _sb_card(e.get("foul_committed", {}), row, tally, k)
        elif typ == "Bad Behaviour":
            _sb_card(e.get("bad_behaviour", {}), row, tally, k)
        elif typ == "Duel":
            d = e["duel"]
            if d["type"]["name"] == "Tackle":
                row["tackles_won_per_team"] += (d.get("outcome", {}).get("name") in
                                                ("Won", "Success", "Success In Play", "Success Out")) / 2
        elif typ == "Interception":
            row["interceptions"] += 1
        elif typ == "Ball Recovery":
            row["ball_recoveries"] += 1
        elif typ == "Clearance":
            row["clearances"] += 1
        elif typ == "Pressure":
            row["pressures"] += 1
        elif typ == "Goal Keeper":
            gt = e["goalkeeper"]["type"]["name"]
            row["keeper_sweeps"] += gt == "Keeper Sweeper"
            row["keeper_claims"] += gt in ("Collected", "Punch")
        elif typ == "Injury Stoppage":
            row["injuries"] += 1
        elif typ == "Substitution":
            row["injury_subs"] += e["substitution"]["outcome"]["name"] == "Injury"
    out = {key: float(row[key]) for key in (
        "goals", "shots", "shots_on_target", "corners", "offsides", "fouls", "yellow_cards", "red_cards",
        "passes", "final_third_passes", "tackles_won_per_team", "interceptions", "clearances", "pressures",
        "keeper_sweeps", "keeper_claims", "injuries", "injury_subs", "crosses", "throw_ins", "goal_kicks",
        "ball_recoveries")}
    out["xg_per_shot"] = float(np.mean(xgs)) if xgs else None
    out["pass_accuracy_pct"] = 100 * row["passes_ok"] / max(row["passes"], 1)
    hsum = max(sum(heights.values()), 1)
    for h in ("ground", "low", "high"):
        out[f"pass_{h}_pct"] = 100 * heights[h] / hsum
    out["loose_first_time_shot_pct"] = 100 * loose_ft / np_shots if np_shots else None
    out["header_shot_pct"] = 100 * headers / np_shots if np_shots else None
    out["counters"] = float(len(counters))
    out["_pens"], out["_pen_goals"] = pens, pen_goals
    return tally.finish(out)


def _sb_card(detail: dict, row: Counter, tally: _Tally, k: int) -> None:
    card = detail.get("card", {}).get("name")
    row["yellow_cards"] += card == "Yellow Card"
    if card in ("Red Card", "Second Yellow"):
        row["red_cards"] += 1
        if tally.red_side is None:
            tally.red_side = k


# --- the card -------------------------------------------------------------------------

# metric: (label, how to compare). A number is a ± tolerance as a share of the real value;
# a tuple is an absolute range taken from the literature section instead of the event data.
CARD = [
    ("goals", "goals per match", 0.12),
    ("shots", "shots per match", 0.12),
    ("shots_on_target", "shots on target", 0.15),
    ("xg_per_shot", "xG per shot", 0.12),
    ("header_shot_pct", "headers, % of non-penalty shots", 0.25),
    ("loose_first_time_shot_pct", "first-time shots, no pass before, %", 0.3),
    ("corners", "corners per match", 0.15),
    ("crosses", "high crosses and corners", 0.2),
    ("throw_ins", "throw-ins", 0.15),
    ("goal_kicks", "goal kicks", 0.2),
    ("offsides", "offsides per match", 0.2),
    ("fouls", "fouls per match", 0.15),
    ("yellow_cards", "yellow cards", 0.2),
    ("red_cards", "red cards (both kinds)", None),
    ("passes", "passes (no throw-ins)", 0.12),
    ("pass_accuracy_pct", "pass accuracy %", 0.04),
    ("pass_ground_pct", "pass height: ground %", 0.06),
    ("pass_low_pct", "pass height: low %", 0.3),
    ("pass_high_pct", "pass height: high %", 0.2),
    ("final_third_passes", "completed passes into final third", 0.2),
    ("tackles_won_per_team", "tackles won per team", 0.25),
    ("interceptions", "interceptions", 0.3),
    ("ball_recoveries", "ball recoveries", 0.3),
    ("clearances", "clearances", 0.3),
    ("pressures", "pressures", 0.2),
    ("counters", "counter-attack possessions", 0.35),
    ("keeper_sweeps", "keeper sweeps (off his line)", 0.4),
    ("keeper_claims", "keeper claims and punches", 0.4),
    ("injuries", "injuries (StatsBomb: injury stoppages)", 0.5),
    ("injury_subs", "substitutions for injury", 0.5),
    ("penalty_conversion", "penalties scored (in play)", 0.1),
    ("late_pass_acc_drop_pts", "pass acc. drop after 75' (points)", None),
    ("leader_shot_share", "leading side's share of shots", 0.08),
    ("leader_pass_share", "leading side's share of passes", 0.06),
    ("back_line_m", "back line, m from own goal", None),
    ("back_line_defending_m", "back line when defending", None),
    ("keeper_x_m", "keeper, m from own goal", None),
    ("lead_line_shift", "leader's line after 70' vs first 20' (defending)", None),
    ("trail_line_shift", "trailer's line after 70' vs first 20' (defending)", None),
    ("var_overturns", "VAR overturns per match", None),
]


def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, (list, tuple)):
        return "/".join(f"{x:.0f}" if abs(x) >= 1 else f"{100 * x:.0f}" for x in v)
    return f"{v:.3f}" if abs(v) < 1 else f"{v:.1f}"


def compare(sim: dict, ref: dict) -> list[tuple]:
    real, lit = ref["wc2022"], ref["literature"]
    rows = []
    for key, label, tol in CARD:
        s = sim.get(key)
        if key in lit:
            lo, hi = lit[key]["range"]
            r = (lo, hi)
            ok = s is not None and lo <= s <= hi
        else:
            r = real.get(key)
            ok = s is not None and r is not None and tol is not None and abs(s - r) <= tol * abs(r)
        rows.append((key, label, s, r, ok))
    return rows


def loss(sim: dict, ref: dict, weights: dict | None = None) -> float:
    """Squared misses in tolerance units, for the parameter search (scripts/realism_tune.py)."""
    real, lit = ref["wc2022"], ref["literature"]
    total = 0.0
    for key, _, tol in CARD:
        w = (weights or {}).get(key, 1.0)
        s = sim.get(key)
        if s is None or not w:
            continue
        if key in lit:
            lo, hi = lit[key]["range"]
            half = (hi - lo) / 2 or 1.0
            miss = max(lo - s, s - hi, 0.0) / half
        elif tol and real.get(key):
            miss = (s - real[key]) / (tol * abs(real[key]))
        else:
            continue
        total += w * miss * miss
    if "results_pct" in sim and "results_pct" in lit:
        target = lit["results_pct"]["value"]
        total += (weights or {}).get("results_pct", 1.0) * sum(((a - b) / 5) ** 2 for a, b in zip(sim["results_pct"], target))
    return total


def print_card(name: str, sim: dict, ref: dict) -> None:
    print(f"\n== {name}: {sim['matches']} simulated matches vs real football ==")
    print(f"{'metric':42} {'sim':>10} {'real':>14}  ok")
    for key, label, s, r, ok in compare(sim, ref):
        rs = f"{r[0]:g}–{r[1]:g}" if isinstance(r, tuple) else _fmt(r)
        print(f"{label:42} {_fmt(s):>10} {rs:>14}  {'✓' if ok else '✗'}")
    real = ref["wc2022"]
    print(f"{'goals by minute, % (0-15 ... 75-90+)':42} {_fmt(sim['goal_minute_share']):>16} "
          f"{_fmt(real['goal_minute_share']):>16}")
    if "results_pct" in sim:
        lit = ref["literature"]["results_pct"]
        print(f"{'home / draw / away %':42} {_fmt(sim['results_pct']):>16}   {_fmt(lit['value']):>14} ({lit['source']})")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=120)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--scenarios", default="demo,mirror,swap")
    ap.add_argument("--red", type=int, default=0, help="also run N paired seeds with an away red card at 38'")
    ap.add_argument("--set", action="append", default=[], help="Params override, e.g. --set foul_rate=0.6")
    ap.add_argument("--build-reference", type=Path, help="StatsBomb open-data folder (matches.json, events/)")
    ap.add_argument("--json", type=Path, help="also write the simulated numbers here")
    args = ap.parse_args()

    if args.build_reference:
        ref = json.loads(REFERENCE.read_text(encoding="utf-8")) if REFERENCE.exists() else {"literature": {}}
        ref["wc2022"] = build_reference(args.build_reference)
        REFERENCE.parent.mkdir(parents=True, exist_ok=True)
        REFERENCE.write_text(json.dumps(ref, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\r\n")
        print(json.dumps(ref["wc2022"], indent=2))
        return

    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    names = {f.name: f.type for f in fields(Params)}
    overrides = {}
    for item in args.set:
        key, value = item.split("=", 1)
        if key not in names:
            raise SystemExit(f"unknown parameter {key}")
        overrides[key] = json.loads(value)
    seeds = range(args.seed, args.seed + args.matches)
    dump = {}
    with ProcessPoolExecutor() as pool:
        for name in args.scenarios.split(","):
            agg = aggregate(run_sim(name, seeds, overrides, None, pool))
            dump[name] = agg
            print_card(name, agg, ref)
        if args.red:
            red_seeds = range(args.seed, args.seed + args.red)
            report = {}
            for plant in (False, True):
                rows = run_sim("demo", red_seeds, overrides, plant, pool)
                after = [r["_red_after"] for r in rows]
                level = [r for r, a in zip(rows, after) if a["level_at_37"]]
                report[plant] = {
                    "home_shot_share": sum(a["home_shots"] for a in after) / max(sum(a["shots"] for a in after), 1),
                    "home_poss": float(np.mean([a["home_poss"] for a in after])),
                    "results_pct": aggregate(rows)["results_pct"],
                    "level_home_win_pct": 100 * sum(r["_result"] == "H" for r in level) / max(len(level), 1),
                    "level_n": len(level),
                }
            dump["red_card"] = {str(k): v for k, v in report.items()}
            lit = ref["literature"]
            print(f"\n== away red card at 38', {args.red} paired seeds (demo pairing) ==")
            print(f"{'':28} {'no red':>12} {'red':>12}   real")
            for key, label, real in (
                ("home_shot_share", "home share of shots", lit["red_11_shot_share"]),
                ("home_poss", "home possession", lit["red_11_possession"]),
            ):
                print(f"{label:28} {report[False][key]:12.2f} {report[True][key]:12.2f}   "
                      f"{real['range'][0]:g}–{real['range'][1]:g} ({real['source']})")
            print(f"{'home / draw / away %':28} {_fmt(report[False]['results_pct']):>12} {_fmt(report[True]['results_pct']):>12}")
            print(f"{'home win % if 0-0 at 37':28} {report[False]['level_home_win_pct']:12.0f} "
                  f"{report[True]['level_home_win_pct']:12.0f}   ({report[True]['level_n']} level games)")
    if args.json:
        args.json.write_text(json.dumps(dump, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
