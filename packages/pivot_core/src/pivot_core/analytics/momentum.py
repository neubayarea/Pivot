"""Per-minute momentum (ADR-0010, MET-024), built the way Opta builds it (The Analyst, "What is
match momentum").

1. Every on-ball action (pass, carry, dribble, shot) gets a possession value: the threat surface
   (ATTR-009) where it starts and, if it worked, where it ends, seen from the team on the ball;
   the higher of the two.
2. Per team and minute, the highest value reached, capped at `CAP`; a minute without an action
   is 0. Passing the ball around adds nothing beyond its best moment, and losing it subtracts
   nothing.
3. Each team's peaks are weighted by recency (EWMA, half-life `HALF_LIFE_MIN`), so the last 3-4
   minutes carry most of the weight; both restart at 0 at the start of each period.
4. momentum = (home - away) / CAP, between -1 and 1: +1 when the home side reached the cap in
   every recent minute and the away side nothing. Positive values mean the home side is on top.

Shots and goals are not separate inputs. B06 adds change-point detection on top of this series.
`threat_home` / `threat_away` keep their meaning: the sum of the team's `threat` that minute.
"""

from __future__ import annotations

from collections import defaultdict

from ..domain import MatchEvent, MinuteMetric
from ..domain.common import attacking_view

CAP = 0.1                            # per team-minute peak; bites on about the top 8% of minutes (ADR-0010)
HALF_LIFE_MIN = 1.5                  # the last 4 minutes hold about 85% of the weight
ON_BALL = ("pass", "carry", "dribble", "shot")


def possession_value(e: MatchEvent) -> float:
    """Highest threat-surface value of where the action starts and, if it worked, where it ends."""
    from ..sim.engine import threat_value             # here, not at the top: sim imports analytics

    points = [e.location]
    if e.type != "shot" and e.outcome == "success" and e.end_location is not None:
        points.append(e.end_location)
    return max(threat_value(attacking_view(p, e.team)) for p in points)


def momentum_series(match_id: str, events: list[MatchEvent]) -> list[MinuteMetric]:
    peak: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
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
        if e.type in ON_BALL and e.location is not None:
            peak[e.minute][side] = max(peak[e.minute][side], min(possession_value(e), CAP))
    if not period_of:
        return []
    decay = 0.5 ** (1 / HALF_LIFE_MIN)
    out: list[MinuteMetric] = []
    home = away = 0.0
    last_period = None
    for minute in range(0, max(period_of) + 1):
        period = period_of.get(minute, last_period)
        if period != last_period:
            home = away = 0.0
            last_period = period
        ph, pa = peak[minute]
        home = decay * home + (1 - decay) * ph
        away = decay * away + (1 - decay) * pa
        th, ta = threat[minute]
        out.append(MinuteMetric(match_id=match_id, minute=minute, momentum=round((home - away) / CAP, 4),
                                threat_home=round(th, 4), threat_away=round(ta, 4),
                                pressure_home=pressure[minute][0], pressure_away=pressure[minute][1]))
    return out
