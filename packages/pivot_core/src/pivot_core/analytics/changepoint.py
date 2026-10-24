"""Momentum alarm (B06, ADR-0010): two-sided CUSUM on the per-minute momentum series.

Defaults give about 3.8 candidates per simulated match (20 matches, scripts/alarm_report.py);
the Judge then keeps the real ones. B09 tunes them further.

How it works, minute by minute within each period:

1. the baseline is the mean momentum of the previous `baseline_min` minutes;
2. two running sums collect how far momentum sits above (S+) or below (S-) that baseline,
   minus a drift `k` so ordinary wobble does not add up;
3. when one sum passes the threshold `h`, the change is placed at the minute that sum last
   started growing from zero, and both sums reset;
4. the candidate is kept only once `confirm_min` minutes after the change are known and the
   swing (mean after minus mean before) still points the same way and is at least `min_swing`;
   both means use minutes of the same period only, at least `min_side_min` on each side, and a
   candidate still waiting when a new period starts is dropped (momentum restarts at the break,
   which is not a turn in the match); within `restart_min` minutes of the restart, a change
   towards the side that was on top before the break, with momentum moving away from zero, is
   dropped too: that is momentum climbing back to where it was, not a turn;
5. candidates closer than `min_gap_min` minutes to the previous one are dropped, and at most
   `max_per_match` are kept.

The same `PivotDetector` runs live (feed it one MinuteMetric at a time, with that minute's new
events or all events so far: it keeps its own copy and ignores repeats) or on a finished match
(`detect_candidates`). A minute pushed twice, or out of order, is ignored. Candidates go to the
Judge (D03); its verdict decides the final severity.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..domain import MatchEvent, MinuteMetric, PivotCandidate

KEY_TYPES = {"substitution", "tactical_shift", "card", "var_review"}


@dataclass
class DetectorParams:
    k: float = 0.1                   # drift: deviations smaller than this never accumulate
    h: float = 1.2                   # alarm threshold on the running sum
    baseline_min: int = 10           # minutes in the baseline mean
    confirm_min: int = 5             # the new level must hold this long (ADR-0010)
    min_swing: float = 0.3           # minimum |mean after - mean before|
    min_side_min: int = 3            # minutes of the same period needed on each side of the change
    restart_min: int = 10            # after a restart, a climb back to the pre-break leader is not a turn
    restart_lead: float = 0.2        # ... when that side's momentum before the break was at least this
    min_gap_min: int = 8             # minutes between two candidates (ADR-0010)
    max_per_match: int = 5           # ADR-0010
    window_before: int = 8           # evidence window handed to the Judge: [minute - 8, minute + 5)
    window_after: int = 5


def key_events(events: list[MatchEvent], window: tuple[int, int]) -> list[str]:
    """Goals, red cards, substitutions, tactical shifts and VAR reviews inside the window."""
    out = []
    for e in events:
        if not window[0] <= e.minute < window[1] or e.period == 5:
            continue
        if e.type == "shot" and e.shot_outcome == "goal":
            out.append(e.event_id)
        elif e.type in KEY_TYPES:
            if e.type == "card" and not (e.foul and e.foul.card in ("red", "second_yellow")):
                continue
            out.append(e.event_id)
    return out


def severity(swing: float, key_ids: list[str], events_by_id: dict[str, MatchEvent]) -> int:
    """ADR-0010: 3 for a big swing or a goal / red card nearby, 2 for a medium swing or a substitution."""
    types = {events_by_id[i].type for i in key_ids if i in events_by_id}
    if abs(swing) >= 0.6 or types & {"shot", "card"}:          # key "shot" ids are goals, key cards are reds
        return 3
    if abs(swing) >= 0.45 or "substitution" in types:
        return 2
    return 1


@dataclass
class _Pending:
    minute: int
    direction: str
    stat: float


@dataclass
class PivotDetector:
    match_id: str
    params: DetectorParams = field(default_factory=DetectorParams)
    series: list[MinuteMetric] = field(default_factory=list)
    _pos: float = 0.0
    _neg: float = 0.0
    _pos_start: int | None = None
    _neg_start: int | None = None
    _period_start: int = 0
    _pending: list[_Pending] = field(default_factory=list)
    _events: dict[str, MatchEvent] = field(default_factory=dict)   # every event seen so far, by id
    _before_break: float = 0.0       # mean momentum of the last 5 minutes of the previous period
    emitted: list[PivotCandidate] = field(default_factory=list)

    def reset_period(self, minute: int) -> None:
        """Call at the first minute of a new period: momentum restarts, so the sums do too, and a
        change still waiting for confirmation is dropped (its after-window would be the restart)."""
        self._pos = self._neg = 0.0
        self._pos_start = self._neg_start = None
        closing = self._momentum(max(self._period_start, minute - 5), minute)
        self._before_break = float(np.mean(closing)) if closing else 0.0
        self._period_start = minute
        self._pending.clear()

    def _climbing_back(self, c: _Pending, before: list[float], after: list[float]) -> bool:
        """Momentum restarts at zero; rising back towards the side that led before the break is no turn."""
        p, lead = self.params, self._before_break
        if c.minute >= self._period_start + p.restart_min or abs(lead) < p.restart_lead:
            return False
        towards_leader = (c.direction == "home") == (lead > 0)
        return towards_leader and abs(float(np.mean(after))) > abs(float(np.mean(before)))

    def _seen_in_order(self) -> list[MatchEvent]:
        return sorted(self._events.values(), key=lambda e: (e.t, e.seq))

    def _momentum(self, lo: int, hi: int) -> list[float]:
        return [m.momentum for m in self.series if lo <= m.minute < hi]

    def push(self, metric: MinuteMetric, events: list[MatchEvent] = ()) -> list[PivotCandidate]:
        """Add one minute; returns the candidates confirmed by it (usually none).
        `events` may be just this minute's new events or everything so far."""
        p = self.params
        for e in events:
            self._events.setdefault(e.event_id, e)
        if self.series and metric.minute <= self.series[-1].minute:
            return []                         # a repeat or an earlier minute: already counted
        self.series.append(metric)
        t = metric.minute
        base = self._momentum(max(self._period_start, t - p.baseline_min), t)
        if len(base) >= 3:
            dev = metric.momentum - float(np.mean(base))
            self._pos = max(0.0, self._pos + dev - p.k)
            self._neg = max(0.0, self._neg - dev - p.k)
            if self._pos > 0 and self._pos_start is None:
                self._pos_start = t
            if self._pos == 0:
                self._pos_start = None
            if self._neg > 0 and self._neg_start is None:
                self._neg_start = t
            if self._neg == 0:
                self._neg_start = None
            if self._pos > p.h:
                self._pending.append(_Pending(self._pos_start, "home", self._pos))
                self._pos = self._neg = 0.0
                self._pos_start = self._neg_start = None
            elif self._neg > p.h:
                self._pending.append(_Pending(self._neg_start, "away", self._neg))
                self._pos = self._neg = 0.0
                self._pos_start = self._neg_start = None
        return self._confirm(t)

    def _confirm(self, now: int) -> list[PivotCandidate]:
        p = self.params
        out = []
        for c in list(self._pending):
            if now < c.minute + p.confirm_min - 1:
                continue
            self._pending.remove(c)
            before = self._momentum(max(self._period_start, c.minute - p.confirm_min), c.minute)
            after = self._momentum(c.minute, c.minute + p.confirm_min)
            if min(len(before), len(after)) < p.min_side_min:
                continue
            swing = float(np.mean(after) - np.mean(before))
            if (swing > 0) != (c.direction == "home") or abs(swing) < p.min_swing:
                continue
            if self._climbing_back(c, before, after):
                continue
            if self.emitted and c.minute - self.emitted[-1].minute < p.min_gap_min:
                continue
            if len(self.emitted) >= p.max_per_match:
                continue
            window = (max(0, c.minute - p.window_before), c.minute + p.window_after)
            cand = PivotCandidate(match_id=self.match_id, minute=c.minute, direction=c.direction,
                                  cusum_stat=round(c.stat, 4), swing=round(swing, 4),
                                  key_event_ids=key_events(self._seen_in_order(), window), window=window)
            self.emitted.append(cand)
            out.append(cand)
        return out


def detect_candidates(match_id: str, metrics: list[MinuteMetric], events: list[MatchEvent],
                      params: DetectorParams | None = None) -> list[PivotCandidate]:
    """Run the detector over a finished match."""
    det = PivotDetector(match_id, params or DetectorParams())
    period_of: dict[int, int] = {}
    by_minute: dict[int, list[MatchEvent]] = {}
    for e in events:
        if e.period != 5:
            period_of.setdefault(e.minute, e.period)
            by_minute.setdefault(e.minute, []).append(e)
    last_period = None
    for m in sorted(metrics, key=lambda m: m.minute):
        period = period_of.get(m.minute, last_period)
        if period != last_period:
            det.reset_period(m.minute)
            last_period = period
        det.push(m, by_minute.get(m.minute, []))      # as live: each minute brings its own events
    return det.emitted
