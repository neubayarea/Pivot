"""Test doubles for the agent code: a dict-backed StatSource and quick event and claim builders."""

from __future__ import annotations

from pivot_core.domain import MatchEvent, StatRef
from pivot_core.domain.stats import STAT_UNITS, Claim


class FakeStats:
    """StatSource backed by a dict of (metric, team, window) -> value; anything else is 0."""

    def __init__(self, values):
        self.values = values

    def compute(self, ref: StatRef) -> float:
        return self.values.get((ref.metric, ref.team, tuple(ref.window)), 0.0)


def event(event_id, minute, type="pass", team="home", **kw):
    seq = int(event_id.rsplit("s", 1)[-1])
    period = 1 if minute < 45 else 2
    t = minute * 60 + 10
    return MatchEvent(match_id="M-test", seq=seq, event_id=event_id, t=t, period=period,
                      period_t=t - (0 if period == 1 else 2700), type=type, team=team, **kw)


def claim(metric, team, window, value):
    return Claim(value=value, unit=STAT_UNITS[metric], stat_ref=StatRef(metric=metric, team=team, window=window))
