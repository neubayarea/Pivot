"""Per-minute momentum (ADR-0010): m_t = tanh(alpha * EWMA(threat_home - threat_away)).

Half-life 5 minutes, reset at the start of each period. Positive values mean the home side
is on top. B06 adds change-point detection on top of this series.
"""

from __future__ import annotations

import math
from collections import defaultdict

from ..domain import MatchEvent, MinuteMetric

HALF_LIFE_MIN = 5.0
ALPHA = 6.0


def momentum_series(match_id: str, events: list[MatchEvent]) -> list[MinuteMetric]:
    threat: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
    pressure: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    period_of: dict[int, int] = {}
    for e in events:
        if e.period == 5:
            continue
        side = 0 if e.team == "home" else 1
        period_of.setdefault(e.minute, e.period)
        threat[e.minute][side] += e.threat
        if e.type == "pressure":
            pressure[e.minute][side] += 1
    if not period_of:
        return []
    decay = 0.5 ** (1 / HALF_LIFE_MIN)
    out: list[MinuteMetric] = []
    ewma, last_period = 0.0, None
    for minute in range(0, max(period_of) + 1):
        period = period_of.get(minute, last_period)
        if period != last_period:
            ewma = 0.0
            last_period = period
        th, ta = threat[minute]
        ewma = decay * ewma + (1 - decay) * (th - ta)
        out.append(MinuteMetric(match_id=match_id, minute=minute, momentum=round(math.tanh(ALPHA * ewma), 4),
                                threat_home=round(th, 4), threat_away=round(ta, 4),
                                pressure_home=pressure[minute][0], pressure_away=pressure[minute][1]))
    return out
