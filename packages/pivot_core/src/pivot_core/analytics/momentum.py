"""Per-minute momentum (ADR-0010): m_t = tanh(alpha * EWMA(threat_home - threat_away)).

Half-life 5 minutes, reset at the start of each period. Positive values mean the home side
is on top. B06 adds change-point detection on top of this series.
"""

from __future__ import annotations

import math
from collections import defaultdict

from ..domain import MatchEvent, MinuteMetric

HALF_LIFE_MIN = 5.0
# Scales typical minute-to-minute threat gaps to roughly ±0.6. 40 since B12: the new simulator
# makes about half the threat a match the old one did (6 vs 13), so 30 gave a flatter curve and
# 2.3 alarms a match instead of 3.3 (40 matches, mean |momentum| 0.30 as before).
ALPHA = 40.0


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
