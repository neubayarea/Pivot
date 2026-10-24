"""StatCalculator (B05): the 23 statistics of the stat vocabulary, computed from a match's events
and tracking frames exactly as docs/data-definitions.md section 4 defines them (MET-001 to MET-023).

Usage:

    calc = StatCalculator(match, events, frames)            # or StatCalculator.from_sim(output)
    calc.compute(StatRef(metric="shots", team="away", window=(63, 68)))

`compute(StatRef) -> float` is the `StatSource` interface the Verifier (D05) calls. The Verifier
must use this class, never its own arithmetic (data definitions, section 4).

Rules shared by every metric:
- the window (a, b) covers elapsed minutes a <= t // 60 < b;
- period 5 (the shootout) never counts;
- with `player_id` set, only that player's events (or positions) count; metrics that only make
  sense for a team (possession, width, PPDA, field tilt) return NaN for a player;
- a ratio with nothing to divide by returns NaN, so no claim can be checked against it.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from ..domain import STAT_UNITS, Match, MatchEvent, StatRef, TrackingFrame
from ..domain.common import PITCH_LENGTH, PITCH_WIDTH, area_of, attacking_view, third_of
from .momentum import momentum_series

DEFENDER_ROLES = {"LB", "CB", "RB", "LWB", "RWB"}
GOAL = (PITCH_LENGTH, PITCH_WIDTH / 2)
OPEN_PATTERNS = {"open_play", "counter"}
DECIMALS = {"count": 0, "pct": 1, "xg": 3, "index": 3, "m": 1, "km": 2, "ratio": 2}
NAN = float("nan")


def _other(team: str) -> str:
    return "away" if team == "home" else "home"


@dataclass
class _Frames:
    t: np.ndarray                       # (n,)
    possession: list[str | None]
    owner: list[str | None]
    pos: dict[str, dict[int, tuple[float, float]]]   # player -> t -> (x, y)


class StatCalculator:
    def __init__(self, match: Match, events: list[MatchEvent], frames: list[TrackingFrame]):
        self.match = match
        self.events = [e for e in events if e.period != 5]
        self.by_id = {e.event_id: e for e in self.events}
        self.team_of = {p.player_id: p.team for t in (match.home, match.away) for p in t.squad}
        self._roles = self._role_timeline()
        self._frames = self._index_frames(frames)
        self._metrics = momentum_series(match.match_id, self.events)
        self._possessions = self._index_possessions()

    @classmethod
    def from_sim(cls, out) -> "StatCalculator":
        return cls(out.match, out.events_as_models(), out.frames_as_models())

    # --- setup -----------------------------------------------------------------------

    def _role_timeline(self) -> dict[str, list[tuple[int, dict[str, str]]]]:
        """For each side, (t, {player_id: role}) from every event that carries a team sheet."""
        out: dict[str, list] = {"home": [], "away": []}
        for side, team in (("home", self.match.home), ("away", self.match.away)):
            out[side].append((0, {s.player_id: s.role for s in team.sheet.starters}))
        for e in self.events:
            if e.team_sheet is not None:
                out[e.team].append((e.t, {s.player_id: s.role for s in e.team_sheet.starters}))
        return out

    def role_at(self, player_id: str, t: int) -> str | None:
        roles = None
        for start, mapping in self._roles[self.team_of.get(player_id, "home")]:
            if start <= t:
                roles = mapping
        return roles.get(player_id) if roles else None

    @staticmethod
    def _index_frames(frames: list[TrackingFrame]) -> _Frames:
        pos: dict[str, dict[int, tuple[float, float]]] = defaultdict(dict)
        for f in frames:
            if f.period == 5:
                continue
            for p in f.players:
                pos[p.player_id][f.t] = (p.x, p.y)
        kept = [f for f in frames if f.period != 5]
        return _Frames(np.array([f.t for f in kept]), [f.possession for f in kept],
                       [f.ball.owner_id for f in kept], pos)

    def _index_possessions(self) -> list[dict]:
        """Possessions in order: id, team in control, play pattern, start t, last on-ball event."""
        seen: dict[int, dict] = {}
        for e in self.events:
            if e.possession_id is None:
                continue
            p = seen.setdefault(e.possession_id, {"id": e.possession_id, "team": None, "pattern": e.play_pattern,
                                                  "start_t": e.t, "last_own": None})
            if e.type in ("pass", "carry", "dribble", "shot") and p["team"] in (None, e.team):
                p["team"] = e.team
                p["last_own"] = e
        return [seen[k] for k in sorted(seen)]

    # --- helpers ---------------------------------------------------------------------

    @staticmethod
    def _in_window(t: int, window: tuple[int, int]) -> bool:
        return window[0] <= t // 60 < window[1]

    def _events(self, ref: StatRef, team: str | None = None, types: tuple[str, ...] = ()) -> list[MatchEvent]:
        team = team or ref.team
        out = []
        for e in self.events:
            if e.team != team or not self._in_window(e.t, ref.window):
                continue
            if types and e.type not in types:
                continue
            if ref.player_id and e.player_id != ref.player_id and team == ref.team:
                continue
            out.append(e)
        return out

    def _frame_idx(self, window: tuple[int, int]) -> np.ndarray:
        minutes = self._frames.t // 60
        return np.flatnonzero((minutes >= window[0]) & (minutes < window[1]))

    def _view(self, point, team: str) -> tuple[float, float]:
        return attacking_view(point, team)

    def _players_at(self, team: str, t: int) -> dict[str, tuple[float, float]]:
        return {pid: frames[t] for pid, frames in self._frames.pos.items()
                if t in frames and self.team_of.get(pid) == team}

    # --- public ----------------------------------------------------------------------

    def compute(self, ref: StatRef) -> float:
        value = getattr(self, f"_m_{ref.metric}")(ref)
        if isinstance(value, float) and math.isnan(value):
            return value
        return round(float(value), DECIMALS[STAT_UNITS[ref.metric]])

    # --- MET-001 to MET-023 ----------------------------------------------------------

    def _m_possession_pct(self, ref: StatRef) -> float:
        if ref.player_id:
            return NAN
        idx = self._frame_idx(ref.window)
        live = [self._frames.possession[i] for i in idx if self._frames.possession[i] is not None]
        return 100 * sum(p == ref.team for p in live) / len(live) if live else NAN

    @staticmethod
    def _countable_pass(e: MatchEvent) -> bool:
        return e.type == "pass" and e.pass_type != "throw_in"

    def _m_passes(self, ref: StatRef) -> float:
        return sum(self._countable_pass(e) for e in self._events(ref, types=("pass",)))

    def _m_pass_accuracy_pct(self, ref: StatRef) -> float:
        passes = [e for e in self._events(ref, types=("pass",)) if self._countable_pass(e)]
        return 100 * sum(e.outcome == "success" for e in passes) / len(passes) if passes else NAN

    def _m_passes_final_third(self, ref: StatRef) -> float:
        return sum(1 for e in self._events(ref, types=("pass",))
                   if e.outcome == "success" and e.end_location and third_of(e.end_location, e.team) == "final")

    def _m_box_entries(self, ref: StatRef) -> float:
        def entry(e: MatchEvent) -> bool:
            if e.outcome != "success" or not e.location or not e.end_location:
                return False
            start, end = area_of(e.location, e.team), area_of(e.end_location, e.team)
            return start not in ("opp_box", "opp_six_yard_box") and end in ("opp_box", "opp_six_yard_box")
        return sum(entry(e) for e in self._events(ref, types=("pass", "carry")))

    def _shots(self, ref: StatRef) -> list[MatchEvent]:
        return self._events(ref, types=("shot",))

    def _m_shots(self, ref: StatRef) -> float:
        return len(self._shots(ref))

    def _m_shots_on_target(self, ref: StatRef) -> float:
        return sum(e.shot_outcome in ("goal", "saved") for e in self._shots(ref))

    def _m_xg(self, ref: StatRef) -> float:
        return sum(e.xg or 0.0 for e in self._shots(ref))

    def _m_threat_total(self, ref: StatRef) -> float:
        return sum(e.threat for e in self._events(ref))

    def _m_pressures(self, ref: StatRef) -> float:
        return len(self._events(ref, types=("pressure",)))

    def _m_tackles_won(self, ref: StatRef) -> float:
        return sum(e.outcome == "success" for e in self._events(ref, types=("tackle",)))

    def _m_interceptions(self, ref: StatRef) -> float:
        return len(self._events(ref, types=("interception",)))

    def _m_duels_won(self, ref: StatRef) -> float:
        return sum(e.outcome == "success" for e in self._events(ref, types=("duel",)))

    def _m_turnovers(self, ref: StatRef) -> float:
        """Possessions of `team` that ended because the opponent took the ball in open play (MET-014)."""
        n = 0
        for prev, nxt in zip(self._possessions, self._possessions[1:]):
            last = prev["last_own"]
            if prev["team"] != ref.team or nxt["team"] != _other(ref.team) or last is None:
                continue
            if last.type == "shot" or nxt["pattern"] not in OPEN_PATTERNS:
                continue
            if not self._in_window(last.t, ref.window):
                continue
            if ref.player_id and last.player_id != ref.player_id:
                continue
            n += 1
        return n

    def _m_momentum_avg(self, ref: StatRef) -> float:
        if ref.player_id:
            return NAN
        vals = [m.momentum for m in self._metrics if ref.window[0] <= m.minute < ref.window[1]]
        if not vals:
            return NAN
        sign = 1.0 if ref.team == "home" else -1.0
        return sign * float(np.mean(vals))

    def _m_line_height_m(self, ref: StatRef) -> float:
        """Out of possession: mean distance of the back line from its own goal line (MET-016)."""
        heights = []
        for i in self._frame_idx(ref.window):
            if self._frames.possession[i] != _other(ref.team):
                continue
            t = int(self._frames.t[i])
            xs = [self._view(p, ref.team)[0] for pid, p in self._players_at(ref.team, t).items()
                  if (pid == ref.player_id if ref.player_id else self.role_at(pid, t) in DEFENDER_ROLES)]
            if xs:
                heights.append(float(np.mean(xs)))
        return float(np.mean(heights)) if heights else NAN

    def _m_team_width_m(self, ref: StatRef) -> float:
        """In possession: spread of the outfield players across the pitch (MET-017)."""
        if ref.player_id:
            return NAN
        widths = []
        for i in self._frame_idx(ref.window):
            if self._frames.possession[i] != ref.team:
                continue
            t = int(self._frames.t[i])
            ys = [p[1] for pid, p in self._players_at(ref.team, t).items() if self.role_at(pid, t) != "GK"]
            if len(ys) >= 2:
                widths.append(max(ys) - min(ys))
        return float(np.mean(widths)) if widths else NAN

    def _m_press_distance_m(self, ref: StatRef) -> float:
        """Opponent in possession: distance from its ball carrier to our nearest player (MET-018)."""
        dists = []
        opp = _other(ref.team)
        for i in self._frame_idx(ref.window):
            owner = self._frames.owner[i]
            if self._frames.possession[i] != opp or not owner or self.team_of.get(owner) != opp:
                continue
            t = int(self._frames.t[i])
            carrier = self._frames.pos[owner].get(t)
            ours = self._players_at(ref.team, t)
            if ref.player_id:
                ours = {k: v for k, v in ours.items() if k == ref.player_id}
            if carrier and ours:
                dists.append(min(math.dist(carrier, p) for p in ours.values()))
        return float(np.mean(dists)) if dists else NAN

    def _m_distance_covered_km(self, ref: StatRef) -> float:
        total = 0.0
        lo, hi = ref.window[0] * 60, ref.window[1] * 60
        for pid, frames in self._frames.pos.items():
            if self.team_of.get(pid) != ref.team or (ref.player_id and pid != ref.player_id):
                continue
            for t, p in frames.items():
                q = frames.get(t + 1)
                if q is not None and lo <= t < hi:
                    total += math.dist(p, q)
        return total / 1000

    @staticmethod
    def progressive(e: MatchEvent) -> bool:
        """ATTR-011, Wyscout's thresholds by half of the pitch."""
        if e.type not in ("pass", "carry") or e.outcome != "success" or not e.location or not e.end_location:
            return False
        if e.pass_type in ("corner", "throw_in"):
            return False
        s, f = attacking_view(e.location, e.team), attacking_view(e.end_location, e.team)
        gain = math.dist(s, GOAL) - math.dist(f, GOAL)
        half = PITCH_LENGTH / 2
        if s[0] < half and f[0] < half:
            return gain >= 30
        if s[0] < half <= f[0]:
            return gain >= 15
        return gain >= 10

    def _m_progressive_passes(self, ref: StatRef) -> float:
        return sum(self.progressive(e) for e in self._events(ref, types=("pass",)))

    def _m_ppda(self, ref: StatRef) -> float:
        """Opponent passes in its own 60% / our defensive actions in that area (MET-021)."""
        if ref.player_id:
            return NAN
        opp = _other(ref.team)
        passes = sum(1 for e in self._events(ref, team=opp, types=("pass",))
                     if e.location and attacking_view(e.location, opp)[0] < 0.6 * PITCH_LENGTH)
        actions = sum(1 for e in self._events(ref, types=("tackle", "interception", "foul", "duel"))
                      if e.location and attacking_view(e.location, ref.team)[0] > 0.4 * PITCH_LENGTH)
        return passes / actions if actions else NAN

    def key_pass(self, shot: MatchEvent) -> MatchEvent | None:
        """The pass linked to this shot (ATTR-010), if any."""
        for rid in shot.related_event_ids:
            e = self.by_id.get(rid)
            if e and e.type == "pass" and e.team == shot.team:
                return e
        return None

    def _m_xa(self, ref: StatRef) -> float:
        total = 0.0
        for shot in self._events(StatRef(metric="xa", team=ref.team, window=ref.window), types=("shot",)):
            kp = self.key_pass(shot)
            if kp and (not ref.player_id or kp.player_id == ref.player_id):
                total += shot.xg or 0.0
        return total

    def _m_field_tilt_pct(self, ref: StatRef) -> float:
        if ref.player_id:
            return NAN

        def final_third_passes(team: str) -> int:
            return sum(1 for e in self._events(ref, team=team, types=("pass",))
                       if e.location and third_of(e.location, team) == "final")
        ours, theirs = final_third_passes(ref.team), final_third_passes(_other(ref.team))
        return 100 * ours / (ours + theirs) if ours + theirs else NAN
