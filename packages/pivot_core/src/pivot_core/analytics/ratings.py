"""Player match ratings and stat lines (RAT-001, PlayerMatchStats).

Every player starts at 6.5 (Sofascore's published baseline) and gains or loses points per
action. Weights are the first-draft values from docs/data-definitions.md section 5 and are
calibrated in B07 so that every position group averages 6.6 to 6.8.
"""

from __future__ import annotations

import math
from collections import defaultdict

from ..domain import PlayerMatchStats
from .stats import DEFENDER_ROLES, StatCalculator

BASE = 6.5
W = {
    "goal": 1.0, "assist": 0.6, "key_pass": 0.15, "shot_on_target": 0.1, "progressive": 0.02,
    "dribble_won": 0.1, "threat": 1.5, "tackle_won": 0.08, "interception": 0.07, "shot_block": 0.15,
    "duel_won": 0.05, "clearance": 0.03, "save_base": 0.15, "save_xg": 0.3, "keeper_conceded": -0.2,
    "defender_conceded": -0.1, "turnover": -0.03, "error_to_shot": -0.3, "foul": -0.05,
    "yellow": -0.3, "red": -1.5, "own_goal": -1.0, "penalty_conceded": -0.8,
}
SPRINT_MS = 7.0                      # 25.2 km/h

# Per-position adjustment so each group averages about 6.7 over 30 simulated matches
# (scripts/rating_report.py). Recompute whenever the weights or the simulator change.
POSITION_OFFSET = {"GK": 0.0, "DF": 0.1, "MF": -0.65, "FW": -0.5}


def player_match_stats(calc: StatCalculator, up_to_t: int | None = None) -> list[PlayerMatchStats]:
    events = [e for e in calc.events if up_to_t is None or e.t <= up_to_t]
    last_frame = int(calc._frames.t.max()) if len(calc._frames.t) else 0
    end_t = up_to_t if up_to_t is not None else max(last_frame, max((e.t for e in events), default=0))
    by_id = {e.event_id: e for e in events}
    score = defaultdict(float)
    line: dict[str, dict] = defaultdict(lambda: defaultdict(float))

    def add(pid: str | None, key: str, n: float = 1.0) -> None:
        if pid:
            score[pid] += W[key] * n

    goals_against: dict[str, list[int]] = {"home": [], "away": []}
    for e in events:
        pid = e.player_id
        s = line[pid] if pid else None
        if e.type == "shot":
            s["shots"] += 1
            s["xg"] += e.xg or 0.0
            if e.shot_outcome in ("goal", "saved"):
                add(pid, "shot_on_target")
            if e.shot_outcome == "goal":
                s["goals"] += 1
                add(pid, "goal")
                goals_against["away" if e.team == "home" else "home"].append(e.t)
            kp = calc.key_pass(e)
            if kp and kp.player_id:
                line[kp.player_id]["key_passes"] += 1
                line[kp.player_id]["xa"] += e.xg or 0.0
                add(kp.player_id, "key_pass")
                if e.shot_outcome == "goal":
                    line[kp.player_id]["assists"] += 1
                    add(kp.player_id, "assist")
        elif e.type == "pass" and pid:
            if e.pass_type != "throw_in":
                s["passes"] += 1
                s["passes_ok"] += e.outcome == "success"
            if StatCalculator.progressive(e):
                s["progressive_passes"] += 1
                add(pid, "progressive")
            if e.outcome == "success":
                add(pid, "threat", e.threat)
            elif e.outcome == "fail":
                add(pid, "turnover")
        elif e.type == "carry" and pid:
            if StatCalculator.progressive(e):
                add(pid, "progressive")
            add(pid, "threat", e.threat)
        elif e.type == "dribble" and pid:
            if e.outcome == "success":
                s["dribbles_won"] += 1
                add(pid, "dribble_won")
            else:
                add(pid, "turnover")
        elif e.type == "tackle" and pid and e.outcome == "success":
            s["tackles_won"] += 1
            add(pid, "tackle_won")
        elif e.type == "interception" and pid:
            s["interceptions"] += 1
            add(pid, "interception")
        elif e.type == "block" and pid:
            if any(by_id.get(r) and by_id[r].type == "shot" for r in e.related_event_ids):
                add(pid, "shot_block")
        elif e.type == "duel" and pid and e.outcome == "success":
            s["duels_won"] += 1
            s["aerials_won"] += e.duel_type == "aerial"
            add(pid, "duel_won")
        elif e.type == "clearance" and pid:
            add(pid, "clearance")
            if e.meta.get("own_goal") == "true":
                add(pid, "own_goal")
        elif e.type == "goalkeeper" and pid:
            if e.keeper_action in ("shot_saved", "shot_parried", "tipped_over"):
                s["saves"] += 1
                shot = next((by_id[r] for r in e.related_event_ids if r in by_id and by_id[r].type == "shot"), None)
                add(pid, "save_base")
                add(pid, "save_xg", shot.xg or 0.0 if shot else 0.0)
            elif e.keeper_action == "goal_conceded":
                add(pid, "keeper_conceded")
        elif e.type == "foul" and pid:
            s["fouls_committed"] += 1
            add(pid, "foul")
            if e.foul and e.foul.penalty_awarded:
                add(pid, "penalty_conceded")
        elif e.type == "card" and pid and e.foul:
            add(pid, "yellow" if e.foul.card == "yellow" else "red")

    # A lost ball that the opponent turns into a shot within 10 seconds is a bigger error.
    shots_by_possession = defaultdict(list)
    for e in events:
        if e.type == "shot" and e.possession_id is not None:
            shots_by_possession[e.possession_id].append(e.t)
    for prev, nxt in zip(calc._possessions, calc._possessions[1:]):
        last = prev["last_own"]
        if last is None or last.outcome != "fail" or nxt["team"] == prev["team"] or (up_to_t and last.t > up_to_t):
            continue
        if any(t - last.t <= 10 for t in shots_by_possession.get(nxt["id"], [])):
            add(last.player_id, "error_to_shot")
            add(last.player_id, "turnover", -1.0)          # replaces the ordinary turnover penalty

    # Defenders on the pitch lose a little for every goal their team concedes.
    for side, times in goals_against.items():
        for t in times:
            for pid, pos in calc._players_at(side, t).items():
                if calc.role_at(pid, t) in DEFENDER_ROLES:
                    score[pid] += W["defender_conceded"]

    out = []
    for team in (calc.match.home, calc.match.away):
        for player in team.squad:
            pid = player.player_id
            frames = {t: p for t, p in calc._frames.pos.get(pid, {}).items() if t <= end_t}
            if not frames:
                continue
            ts = sorted(frames)
            speeds = [math.dist(frames[a], frames[b]) for a, b in zip(ts, ts[1:]) if b == a + 1]
            sprints = sum(1 for a, b in zip([0.0] + speeds, speeds) if a < SPRINT_MS <= b)
            s = line[pid]
            rating = min(10.0, max(3.0, BASE + score[pid] + POSITION_OFFSET[player.position]))
            out.append(PlayerMatchStats(
                match_id=calc.match.match_id, player_id=pid, up_to_t=end_t,
                minutes_played=min(180, len(frames) // 60), rating=round(rating, 1),
                goals=int(s["goals"]), assists=int(s["assists"]), shots=int(s["shots"]),
                xg=round(s["xg"], 2), xa=round(s["xa"], 2), passes=int(s["passes"]),
                pass_accuracy_pct=round(100 * s["passes_ok"] / s["passes"], 1) if s["passes"] else None,
                key_passes=int(s["key_passes"]), progressive_passes=int(s["progressive_passes"]),
                dribbles_won=int(s["dribbles_won"]), tackles_won=int(s["tackles_won"]),
                interceptions=int(s["interceptions"]), duels_won=int(s["duels_won"]),
                aerials_won=int(s["aerials_won"]), fouls_committed=int(s["fouls_committed"]),
                saves=int(s["saves"]), distance_km=round(min(sum(speeds) / 1000, 20.0), 2),
                top_speed_kmh=round(min(max(speeds, default=0.0) * 3.6, 45.0), 1), sprints=sprints,
            ))
    return out
