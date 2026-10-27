#!/usr/bin/env python3
"""How real does a simulated match look? The same numbers on N simulated matches and on real
football, side by side (B12).

  uv run scripts/realism_scorecard.py                       # 120 matches per scenario
  uv run scripts/realism_scorecard.py --matches 240 --red 120
  uv run scripts/realism_scorecard.py --build-reference <statsbomb dir> --as pl1516
  uv run scripts/realism_scorecard.py --build-recent E0_2324.csv E0_2425.csv
  uv run scripts/realism_scorecard.py --set-pieces --matches 80   # where players stand at corners and free kicks
  uv run scripts/realism_scorecard.py --styled                    # each coach's own tactics, as on the site (Bx13)

Real numbers come from eval/realism/reference.json, Premier League first (REAL_ORDER):

- "pl_recent": the last two Premier League seasons (2023/24, 2024/25, 760 matches) from the
  football-data.co.uk match files: results, goals, shots, fouls, corners, cards.
- "pl1516": StatsBomb open data, Premier League 2015/16 (380 matches), for everything the
  match files do not have (passes, pass height, offsides, tackles, xG, conditional effects).
- "wc2022": StatsBomb open data, 2022 World Cup (64 matches), kept for comparison only.
- "literature": what event data cannot give (line height, VAR, red-card effects), with the
  source next to each number.
Event data is regular time only (periods 1 and 2); the raw files are never committed.

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
from pivot_core.sim.formations import DEFENDER_ROLES as DEFENDERS
from pivot_core.sim.tactics import styled as with_styles

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "eval" / "realism" / "reference.json"
L, W = 105.0, 68.0
BINS = (15, 30, 45, 60, 75, 90)                   # goals by minute: 0-15, ..., 75-90+ (stoppage in the last bin)
REAL_ORDER = ("pl_recent", "pl1516")              # where a real number is taken from, first that has it
DEF_ACTIONS = ("interception", "clearance", "block", "ball_recovery", "duel", "tackle", "foul")
PRESS_ACTIONS = ("tackle", "interception", "foul", "duel")   # MET-021
SB_DEF = {"Interception": "interception", "Clearance": "clearance", "Block": "block", "Ball Recovery": "ball_recovery",
          "Duel": "duel", "Foul Committed": "foul"}

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
        self.def_x: list[float] = []               # defenders' defensive actions, metres from own goal
        self.build_passes = [0, 0]                 # passes in the passer's own 60 % (PPDA numerator)
        self.press_actions = [0, 0]                # defensive actions in the opponent's 60 % (MET-021)

    def defending(self, k: int, kind: str, x: float, defender: bool) -> None:
        """A defensive action by side k at x metres from its own goal."""
        if defender and kind in DEF_ACTIONS:
            self.def_x.append(x)
        if kind in PRESS_ACTIONS and x > 0.4 * L:
            self.press_actions[k] += 1

    def build_pass(self, k: int, x: float) -> None:
        if x < 0.6 * L:
            self.build_passes[k] += 1

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
        row["def_action_height_m"] = float(np.mean(self.def_x)) if self.def_x else None
        ppda = [self.build_passes[1 - k] / self.press_actions[k] for k in (0, 1) if self.press_actions[k]]
        row["ppda"] = float(np.mean(ppda)) if ppda else None
        return row


# --- simulated matches ----------------------------------------------------------------

def _gk_slots(out, k: int) -> np.ndarray:
    team = out.match.home if k == 0 else out.match.away
    gk = {s.player_id for s in team.sheet.starters if s.role == "GK"}
    return np.array([[pid in gk for pid in ids[k]] for ids in out.frames_ids])


def _roles(ev: list[dict]) -> dict[str, str]:
    """Each player's role, from every team sheet the match published (later sheets win)."""
    roles = {}
    for e in ev:
        for s in (e.get("team_sheet") or {}).get("starters", []):
            roles[s["player_id"]] = s["role"]
    return roles


def sim_metrics(out) -> dict:
    ev = out.events
    by_id = {e["event_id"]: e for e in ev}
    side = {"home": 0, "away": 1}
    roles = _roles(ev)
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
        if typ in DEF_ACTIONS and e.get("location"):
            x = e["location"][0] if k == 0 else L - e["location"][0]
            tally.defending(k, typ, x, roles.get(e["player_id"]) in DEFENDERS)
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
            sx = e["location"][0] if k == 0 else L - e["location"][0]
            tally.build_pass(k, sx)
            if pt == "throw_in":
                continue
            row["passes"] += 1
            row["passes_ok"] += ok
            heights[e.get("pass_height")] += 1
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
            row["var_goals_disallowed"] += e["var"]["review_of"] == "goal" and e["var"]["decision"] == "overturned"
    out_row = {key: float(row[key]) for key in (
        "goals", "shots", "shots_on_target", "corners", "offsides", "fouls", "yellow_cards", "red_cards",
        "passes", "final_third_passes", "tackles_won_per_team", "interceptions", "clearances", "pressures",
        "keeper_sweeps", "keeper_claims", "injuries", "injury_subs", "var_overturns", "var_goals_disallowed",
        "crosses", "throw_ins", "goal_kicks", "ball_recoveries")}
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


def _build(scenario: str, seed: int, styled: bool):
    m = build_demo_match(seed, **SCENARIOS[scenario])
    return with_styles(m) if styled else m


def _run_one(job: tuple) -> dict:
    scenario, seed, overrides, plant, styled = job
    m = _build(scenario, seed, styled)
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
            pool: ProcessPoolExecutor | None = None, styled: bool = False) -> list[dict]:
    jobs = [(scenario, s, overrides or {}, plant, styled) for s in seeds]
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
    agg["first_half_goals_pct"] = 100 * float(bins[:3].sum()) / max(float(bins.sum()), 1.0)
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


def build_recent(files: list[Path]) -> dict:
    """Per-match averages from football-data.co.uk match files (one row per match, full time)."""
    import csv
    rows = [r for f in files for r in csv.DictReader(f.open(encoding="utf-8-sig", errors="replace"))]
    n = len(rows)

    def both(h: str, a: str) -> list[float]:
        return [float(r[h]) + float(r[a]) for r in rows]

    goals = both("FTHG", "FTAG")
    out = {key: float(np.mean(both(h, a))) for key, h, a in (
        ("goals", "FTHG", "FTAG"), ("shots", "HS", "AS"), ("shots_on_target", "HST", "AST"), ("fouls", "HF", "AF"),
        ("corners", "HC", "AC"), ("yellow_cards", "HY", "AY"), ("red_cards", "HR", "AR"))}
    out["results_pct"] = [100 * sum(r["FTR"] == x for r in rows) / n for x in "HDA"]
    out["first_half_goals_pct"] = 100 * sum(both("HTHG", "HTAG")) / sum(goals)
    out["matches"] = n
    out["source"] = "football-data.co.uk, " + ", ".join(f.name for f in files)
    return out


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
        if typ in SB_DEF and e.get("location"):
            tally.defending(k, SB_DEF[typ], e["location"][0] * L / 120, "Back" in e.get("position", {}).get("name", ""))
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
            tally.build_pass(k, e["location"][0] * L / 120)
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
    ("first_half_goals_pct", "goals in the first half, %", 0.1),
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
    ("ppda", "PPDA (passes allowed per defensive action)", 0.2),
    ("def_action_height_m", "defenders' defensive actions, m from goal", 0.08),
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
    ("var_goals_disallowed", "goals ruled out by VAR per match", None),
]


# --- set pieces (Ax44) -----------------------------------------------------------------
# Who stands where at corners and free kicks, counted in the tracking frames the same way
# scripts/setpiece_reference.py counts the Premier League's shot freeze frames
# (reference.json "set_pieces_pl1516"). The sim is read at the kick (the last frame before it,
# as the match page reads it) and, for shots soon after a corner, at the shot as well.

def _sp_view(xy: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Metres from the goal `k` attacks, and y in k's view."""
    x = xy[..., 0] if k == 0 else L - xy[..., 0]
    y = xy[..., 1] if k == 0 else W - xy[..., 1]
    return L - x, y


def _sp_box(d, y) -> np.ndarray:
    return (d <= 16.5) & (y >= 13.84) & (y <= 54.16)


def _sp_six(d, y) -> np.ndarray:
    return (d <= 5.5) & (y >= 24.84) & (y <= 43.16)


def _sp_frame(out, n: int, k: int, taker: str | None) -> tuple:
    """Attackers (taker aside), outfield defenders and the defending keeper of frame n, in k's view."""
    ids = out.frames_ids[n]
    gk = {s.player_id for team in (out.match.home, out.match.away) for s in team.sheet.starters if s.role == "GK"}
    pos = out.frames_pos[n]
    att = [i for i, pid in enumerate(ids[k]) if pid and pid != taker]
    dfn = [j for j, pid in enumerate(ids[1 - k]) if pid and pid not in gk]
    keeper = [j for j, pid in enumerate(ids[1 - k]) if pid in gk]
    return (_sp_view(pos[k, att], k), _sp_view(pos[1 - k, dfn], k),
            _sp_view(pos[1 - k, keeper], k) if keeper else None)


def setpiece_rows(out) -> dict:
    """One row per corner (at the kick and, for a shot within 6 s, at the shot) and per free kick
    within 40 m of goal (at the kick)."""
    t = out.frames_t
    rows: dict = {"corners": [], "corner_shots": [], "free_kicks": [], "jumps": 0, "player_seconds": 0}
    ev = out.events
    side = {"home": 0, "away": 1}
    last_corner: dict | None = None
    for e in ev:
        kind = e.get("pass_type") if e["type"] == "pass" else None
        if e["type"] == "shot" and e.get("play_pattern") == "free_kick" and not any(
                p["type"] in ("pass", "carry", "shot") and p.get("possession_id") == e.get("possession_id")
                and p["t"] < e["t"] for p in ev if p.get("possession_id") == e.get("possession_id") and p is not e):
            kind = "free_kick"
        if e["type"] == "shot" and last_corner and last_corner["team"] == e["team"] and e["t"] - last_corner["t"] <= 6:
            n = int(np.searchsorted(t, e["t"]))
            if n < len(t) and t[n] == e["t"]:
                rows["corner_shots"].append(_sp_corner(out, n, side[e["team"]], e["player_id"], None, shooter=True))
        if kind not in ("corner", "free_kick"):
            continue
        n = int(np.searchsorted(t, e["t"])) - 1
        if n < 0:
            continue
        k = side[e["team"]]
        if kind == "corner":
            last_corner = e
            rows["corners"].append(_sp_corner(out, n, k, e["player_id"], out.frames_ball[n]))
            continue
        bd, by = _sp_view(out.frames_ball[n][:2], k)
        dist = float(np.sqrt(bd * bd + (by - 34) ** 2))
        if dist >= 40:
            continue
        a, (dd, dy), keeper = _sp_frame(out, n, k, e["player_id"])
        vx, vy = dd - bd, dy - by
        gx, gy = -bd, 34.0 - by
        r = np.sqrt(vx * vx + vy * vy)
        cos = (vx * gx + vy * gy) / np.maximum(r * np.sqrt(gx * gx + gy * gy), 1e-9)
        cone = (r >= 1.5) & (r <= 12) & (np.degrees(np.arccos(np.clip(cos, -1, 1))) <= 25)
        dists = r[cone]
        line = dists[dists <= dists.min() + 1.5] if len(dists) else dists
        row = {"dist": dist, "wide": abs(float(by) - 34), "wall": int(cone.sum()), "wall_line": len(line),
               "nearest_def_m": float(r.min()) if len(r) else None,
               "def_box": int(_sp_box(dd, dy).sum()), "att_box": int(_sp_box(*a).sum())}
        if len(line):
            row["wall_m"] = float(line.mean())
        if keeper is not None:
            row["keeper_m"] = float(keeper[0][0])
        rows["free_kicks"].append(row)
    step = np.sqrt(((out.frames_pos[1:] - out.frames_pos[:-1]) ** 2).sum(-1))
    live = (out.frames_period[1:] == out.frames_period[:-1])[:, None, None]
    rows["jumps"] = int(((step > 11.0) & live).sum())             # faster than anyone runs
    rows["player_seconds"] = int(live.sum()) * 22
    return rows


def _sp_corner(out, n: int, k: int, taker: str | None, ball, shooter: bool = False) -> dict:
    (ad, ay), (dd, dy), keeper = _sp_frame(out, n, k, None if shooter else taker)
    row = {"att_box": int(_sp_box(ad, ay).sum()), "def_box": int(_sp_box(dd, dy).sum()),
           "att_six": int(_sp_six(ad, ay).sum()), "def_six": int(_sp_six(dd, dy).sum()),
           "att_edge": int(((ad > 16.5) & (ad <= 25) & (np.abs(ay - 34) <= 16)).sum()),
           "def_upfield": int((dd > 30).sum()), "att_back": int((ad > 52.5).sum())}
    if keeper is not None:
        row["keeper_m"] = float(keeper[0][0])
    if ball is not None:
        near = 37.66 if _sp_view(ball[:2], k)[1] > 34 else 30.34
        far = 30.34 if near > 34 else 37.66
        row["near_post"] = bool(((dd <= 2) & (np.abs(dy - near) <= 2.5)).any())
        row["far_post"] = bool(((dd <= 2) & (np.abs(dy - far) <= 2.5)).any())
    return row


def _run_setpieces(job: tuple) -> dict:
    scenario, seed, styled = job
    return setpiece_rows(Engine(_build(scenario, seed, styled), seed).run())


def setpiece_card(rows: list[dict], ref: dict) -> list[tuple]:
    """(label, sim, PL, PL p10-p90) rows for the set-piece comparison."""
    from setpiece_reference import FK_BINS, _stats
    pl = ref.get("set_pieces_pl1516", {})
    corners = [r for m in rows for r in m["corners"]]
    shots = [r for m in rows for r in m["corner_shots"]]
    fks = [r for m in rows for r in m["free_kicks"]]
    out = []

    def add(label, vals, real):
        st = _stats(vals)
        out.append((label, st.get("mean"), st.get("n", 0), real.get("mean") if real else None,
                    f"{real['p10']:g}–{real['p90']:g}" if real and "p10" in real else ""))

    pc = pl.get("corners", {})
    for key, label in (("att_box", "corner: attackers in the box"), ("def_box", "corner: defenders in the box"),
                       ("att_six", "corner: attackers in the six-yard box"),
                       ("def_six", "corner: defenders in the six-yard box"), ("att_edge", "corner: attackers on the edge"),
                       ("keeper_m", "corner: keeper off his line, m"), ("att_back", "corner: attackers in own half"),
                       ("def_upfield", "corner: defenders left upfield")):
        # the broadcast camera behind the freeze frames rarely shows the players left back
        real = None if key in ("att_back", "def_upfield") else pc.get(key)
        add(label + " (kick)", [r[key] for r in corners if key in r], real)
        if key in ("att_box", "def_box", "att_six", "def_six"):
            add(label + " (shot)", [r[key] for r in shots if key in r], pc.get(key))
    for key, label in (("near_post", "corner: man on the near post, share"), ("far_post", "corner: man on the far post, share")):
        vals = [float(r[key]) for r in corners if key in r]
        out.append((label, float(np.mean(vals)) if vals else None, len(vals), pc.get(f"{key}_share"), ""))
    direct = pl.get("direct_free_kicks", {})
    shooting = [r for r in fks if r["dist"] < 32 and r["wide"] < 18]
    add("free kick < 32 m: wall to ball, m", [r["wall_m"] for r in shooting if "wall_m" in r], direct.get("all", {}).get("wall_m"))
    add("free kick < 32 m: nearest defender, m", [r["nearest_def_m"] for r in shooting if r["nearest_def_m"] is not None],
        direct.get("all", {}).get("nearest_def_m"))
    for lo, hi in FK_BINS:
        name = f"{lo}-{hi}m" if hi < 99 else f"{lo}m+"
        part = [r for r in shooting if lo <= r["dist"] < hi]
        real = direct.get("by_distance", {}).get(name, {})
        add(f"free kick {name}: in the wall", [r["wall_line"] for r in part], real.get("wall_line"))
        add(f"free kick {name}: defenders in the box", [r["def_box"] for r in part], real.get("def_box"))
        add(f"free kick {name}: attackers in the box", [r["att_box"] for r in part], real.get("att_box"))
    jumps = sum(m["jumps"] for m in rows) / max(sum(m["player_seconds"] for m in rows), 1)
    out.append(("frames: player steps > 11 m in a second, per 10k", 1e4 * jumps, len(rows), None, ""))
    return out


def print_setpieces(rows: list[dict], ref: dict) -> None:
    print(f"\n== set pieces: {len(rows)} simulated matches vs Premier League 2015/16 (StatsBomb freeze frames) ==")
    print(f"{'':52} {'sim':>7} {'n':>6} {'PL':>7}  PL p10–p90")
    for label, s, n, r, band in setpiece_card(rows, ref):
        print(f"{label:52} {_fmt(s):>7} {n:>6} {_fmt(r):>7}  {band}")


def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, (list, tuple)):
        return "/".join(f"{x:.0f}" if abs(x) >= 1 else f"{100 * x:.0f}" for x in v)
    return f"{v:.3f}" if abs(v) < 1 else f"{v:.1f}"


def real_value(ref: dict, key: str) -> tuple:
    """(value or (low, high), where it comes from) for a metric: a literature range, else the
    first data set in REAL_ORDER that has it."""
    lit = ref["literature"]
    if key in lit and "range" in lit[key]:
        return tuple(lit[key]["range"]), "lit"
    for name in REAL_ORDER:
        v = ref.get(name, {}).get(key)
        if v is not None:
            return v, name
    return None, "-"


def compare(sim: dict, ref: dict) -> list[tuple]:
    rows = []
    for key, label, tol in CARD:
        s = sim.get(key)
        r, src = real_value(ref, key)
        if isinstance(r, tuple):
            ok = s is not None and r[0] <= s <= r[1]
        else:
            ok = s is not None and r is not None and tol is not None and abs(s - r) <= tol * abs(r)
        rows.append((key, label, s, r, ok, src))
    return rows


def loss(sim: dict, ref: dict, weights: dict | None = None) -> float:
    """Squared misses in tolerance units, for the parameter search (scripts/realism_tune.py)."""
    total = 0.0
    for key, _, tol in CARD:
        w = (weights or {}).get(key, 1.0)
        s = sim.get(key)
        if s is None or not w:
            continue
        r, _ = real_value(ref, key)
        if isinstance(r, tuple):
            lo, hi = r
            half = (hi - lo) / 2 or 1.0
            miss = max(lo - s, s - hi, 0.0) / half
        elif tol and r:
            miss = (s - r) / (tol * abs(r))
        else:
            continue
        total += w * miss * miss
    target, _ = real_value(ref, "results_pct")
    if "results_pct" in sim and target is not None:
        total += (weights or {}).get("results_pct", 1.0) * sum(((a - b) / 5) ** 2 for a, b in zip(sim["results_pct"], target))
    return total


def print_card(name: str, sim: dict, ref: dict) -> None:
    print(f"\n== {name}: {sim['matches']} simulated matches vs real football ==")
    print(f"{'metric':42} {'sim':>10} {'real':>14} {'from':>9}  ok")
    for key, label, s, r, ok, src in compare(sim, ref):
        rs = f"{r[0]:g}–{r[1]:g}" if isinstance(r, tuple) else _fmt(r)
        print(f"{label:42} {_fmt(s):>10} {rs:>14} {src:>9}  {'✓' if ok else '✗'}")
    shares, src = real_value(ref, "goal_minute_share")
    print(f"{'goals by minute, % (0-15 ... 75-90+)':42} {_fmt(sim['goal_minute_share']):>16} {_fmt(shares):>16} ({src})")
    if "results_pct" in sim:
        target, src = real_value(ref, "results_pct")
        print(f"{'home / draw / away %':42} {_fmt(sim['results_pct']):>16}   {_fmt(target):>14} ({src})")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=120)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--scenarios", default="demo,mirror,swap")
    ap.add_argument("--red", type=int, default=0, help="also run N paired seeds with an away red card at 38'")
    ap.add_argument("--set", action="append", default=[], help="Params override, e.g. --set foul_rate=0.6")
    ap.add_argument("--build-reference", type=Path, help="StatsBomb open-data folder (matches.json, events/)")
    ap.add_argument("--as", dest="ref_name", default="pl1516", help="name of the data set --build-reference writes")
    ap.add_argument("--build-recent", type=Path, nargs="+", help="football-data.co.uk E0.csv files")
    ap.add_argument("--json", type=Path, help="also write the simulated numbers here")
    ap.add_argument("--set-pieces", action="store_true", help="only the set-piece positions (Ax44)")
    ap.add_argument("--styled", action="store_true", help="each coach's style and tactics, as the site's matches (Bx13)")
    args = ap.parse_args()

    if args.build_reference or args.build_recent:
        ref = json.loads(REFERENCE.read_text(encoding="utf-8")) if REFERENCE.exists() else {"literature": {}}
        name = args.ref_name if args.build_reference else "pl_recent"
        ref[name] = build_reference(args.build_reference) if args.build_reference else build_recent(args.build_recent)
        REFERENCE.parent.mkdir(parents=True, exist_ok=True)
        REFERENCE.write_text(json.dumps(ref, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\r\n")
        print(json.dumps(ref[name], indent=2))
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
    if args.set_pieces:
        with ProcessPoolExecutor() as pool:
            rows = list(pool.map(_run_setpieces, [(name, s, args.styled) for name in args.scenarios.split(",") for s in seeds],
                                 chunksize=2))
        print_setpieces(rows, ref)
        return
    dump = {}
    with ProcessPoolExecutor() as pool:
        for name in args.scenarios.split(","):
            agg = aggregate(run_sim(name, seeds, overrides, None, pool, args.styled))
            dump[name] = agg
            print_card(name, agg, ref)
        if args.red:
            red_seeds = range(args.seed, args.seed + args.red)
            report = {}
            for plant in (False, True):
                rows = run_sim("demo", red_seeds, overrides, plant, pool, args.styled)
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
