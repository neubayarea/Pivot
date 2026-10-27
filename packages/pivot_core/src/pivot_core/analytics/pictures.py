"""Whole-match pictures (Bx12): the shot map, heatmaps, pass networks and average positions.

Pure functions over a match's events and tracking frames; the API cuts both lists (`up_to`,
`period`) before calling them. Every point is in the acting team's attacking view (CONV-002):
the team's own goal at x = 0, the opponent's at x = 105, so both teams' pictures read the same
way. A page that puts the two teams on one pitch flips the away side back: (105 - x, 68 - y).

- Heatmaps count where players spent their time, one sample per player per tracking frame
  (a second). Without frames they count where the players' on-ball events happened instead;
  `source` says which. Cells are shares of the largest cell, 0 to 1. A team's grid counts its
  outfield players only (the keeper has a grid of their own).
- The pass network is each side's starting eleven: where each stood on average while their team
  had the ball, and the completed passes between two of them (at least `min_passes`).
- The penalty shootout (period 5) is left out of everything, like the stat vocabulary does.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from ..domain import Match, MatchEvent, TrackingFrame
from ..domain.common import PITCH_LENGTH, PITCH_WIDTH, attacking_view

HEAT_COLS, HEAT_ROWS = 21, 14                # 5 m by about 4.9 m cells
MIN_PASSES = 3                               # fewest completed passes for a pass-network line


def _view(p: Iterable[float], side: str) -> tuple[float, float]:
    x, y = attacking_view(tuple(p), side)
    return (min(max(x, 0.0), PITCH_LENGTH), min(max(y, 0.0), PITCH_WIDTH))


def _r(v: float, n: int = 1) -> float:
    return round(v, n)


def _played(events: list[MatchEvent]) -> list[MatchEvent]:
    return [e for e in events if e.period != 5]


def shots(events: list[MatchEvent]) -> list[dict]:
    """Every shot in time order, from the shooter's attacking view."""
    out = []
    for e in _played(events):
        if e.type != "shot" or e.location is None:
            continue
        x, y = _view(e.location, e.team)
        end = _view(e.end_location, e.team) if e.end_location else None
        out.append({"event_id": e.event_id, "t": e.t, "period": e.period, "clock_label": e.clock_label,
                    "team": e.team, "player_id": e.player_id, "x": _r(x), "y": _r(y),
                    "end_x": _r(end[0]) if end else None, "end_y": _r(end[1]) if end else None,
                    "xg": e.xg, "outcome": e.shot_outcome, "body_part": e.body_part, "play_pattern": e.play_pattern,
                    "technique": e.shot_technique, "under_pressure": bool(e.under_pressure),
                    "first_time": bool(e.first_time)})
    return out


def _cell(x: float, y: float, cols: int, rows: int) -> int:
    c = min(int(x / PITCH_LENGTH * cols), cols - 1)
    r = min(int(y / PITCH_WIDTH * rows), rows - 1)
    return r * cols + c


def _grid(counts: dict[int, float], cols: int, rows: int) -> list[float]:
    top = max(counts.values(), default=0.0)
    return [_r(counts.get(i, 0.0) / top, 3) if top else 0.0 for i in range(cols * rows)]


def heatmaps(match: Match, events: list[MatchEvent], frames: list[TrackingFrame],
             cols: int = HEAT_COLS, rows: int = HEAT_ROWS) -> dict:
    """Per team and per player: `cells` (row-major, rows along y from the team's right touchline,
    columns along x from its own goal), each a share of the largest cell, and `samples` counted."""
    side_of = {p.player_id: p.team for t in (match.home, match.away) for p in t.squad}
    team = {s: defaultdict(float) for s in ("home", "away")}
    player: dict[str, defaultdict] = defaultdict(lambda: defaultdict(float))
    frames = [f for f in frames if f.period != 5]
    source = "frames" if frames else "events"
    if frames:
        points = ((p.player_id, (p.x, p.y)) for f in frames for p in f.players)
    else:
        points = ((e.player_id, e.location) for e in _played(events) if e.player_id and e.location)
    keepers = {p.player_id for t in (match.home, match.away) for p in t.squad if p.role == "GK"}
    for pid, xy in points:
        side = side_of.get(pid)
        if side is None:
            continue
        i = _cell(*_view(xy, side), cols, rows)
        if pid not in keepers:                   # a keeper's box would drown out the team's picture
            team[side][i] += 1
        player[pid][i] += 1
    return {
        "source": source, "cols": cols, "rows": rows,
        "teams": {s: {"samples": int(sum(c.values())), "cells": _grid(c, cols, rows)} for s, c in team.items()},
        "players": {pid: {"team": side_of[pid], "samples": int(sum(c.values())), "cells": _grid(c, cols, rows)}
                    for pid, c in player.items()},
    }


def _mean_positions(frames: list[TrackingFrame], side_of: dict[str, str], keep) -> dict[str, tuple[float, float, int]]:
    sums: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0])
    for f in frames:
        for p in f.players:
            side = side_of.get(p.player_id)
            if side is None or not keep(f, side):
                continue
            x, y = _view((p.x, p.y), side)
            s = sums[p.player_id]
            s[0] += x
            s[1] += y
            s[2] += 1
    return {pid: (s[0] / s[2], s[1] / s[2], int(s[2])) for pid, s in sums.items()}


def average_positions(match: Match, frames: list[TrackingFrame]) -> list[dict]:
    """Everyone who was on the pitch: mean position with their team on the ball, and off it."""
    side_of = {p.player_id: p.team for t in (match.home, match.away) for p in t.squad}
    frames = [f for f in frames if f.period != 5]
    with_ball = _mean_positions(frames, side_of, lambda f, side: f.possession == side)
    without = _mean_positions(frames, side_of, lambda f, side: f.possession is not None and f.possession != side)
    on = _mean_positions(frames, side_of, lambda f, side: True)
    out = []
    for team in (match.home, match.away):
        for p in team.squad:
            if p.player_id not in on:
                continue
            a, b = with_ball.get(p.player_id), without.get(p.player_id)
            out.append({"player_id": p.player_id, "team": team.side, "seconds": on[p.player_id][2],
                        "in_possession": {"x": _r(a[0]), "y": _r(a[1])} if a else None,
                        "out_of_possession": {"x": _r(b[0]), "y": _r(b[1])} if b else None})
    return out


def pass_networks(match: Match, events: list[MatchEvent], frames: list[TrackingFrame],
                  min_passes: int = MIN_PASSES) -> dict[str, dict]:
    """Per side: the starting eleven as nodes (mean position in possession, passes made and
    received) and the completed passes between two of them as edges, `min_passes` or more."""
    side_of = {p.player_id: p.team for t in (match.home, match.away) for p in t.squad}
    frames = [f for f in frames if f.period != 5]
    where = _mean_positions(frames, side_of, lambda f, side: f.possession == side)
    on_ball: dict[str, list[tuple[float, float]]] = defaultdict(list)
    made, received, pairs = defaultdict(int), defaultdict(int), defaultdict(int)
    for e in _played(events):
        if e.player_id and e.location and e.team == side_of.get(e.player_id):
            on_ball[e.player_id].append(_view(e.location, e.team))
        if e.type == "pass" and e.outcome == "success" and e.player_id and e.receiver_id:
            made[e.player_id] += 1
            received[e.receiver_id] += 1
            pairs[e.player_id, e.receiver_id] += 1
    out = {}
    for team in (match.home, match.away):
        eleven = [s.player_id for s in sorted(team.sheet.starters, key=lambda s: s.slot)]
        nodes = []
        for pid in eleven:
            if pid in where:
                x, y, _ = where[pid]
            elif on_ball.get(pid):                   # no frames: where their on-ball events were
                pts = on_ball[pid]
                x, y = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
            else:
                continue
            nodes.append({"player_id": pid, "x": _r(x), "y": _r(y), "passes": made[pid], "received": received[pid]})
        placed = {n["player_id"] for n in nodes}
        edges = [{"from_id": a, "to_id": b, "passes": n} for (a, b), n in sorted(pairs.items(), key=lambda kv: -kv[1])
                 if n >= min_passes and a in placed and b in placed]
        out[team.side] = {"source": "frames" if where else "events", "nodes": nodes, "edges": edges}
    return out
