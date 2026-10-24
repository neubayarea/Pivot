"""Broadcast overlay (FR-26, rules' Render step): checked pivots as cards timed on the match clock."""

from __future__ import annotations

import re

from pivot_core.domain import (
    OVERLAY_CARD_SECONDS,
    Match,
    MatchEvent,
    OverlayCard,
    OverlayFrame,
    OverlayScoreboard,
    OverlayTimeline,
    Pivot,
    Score,
    clock_label,
)

MAX_CLOCK = 3 * 3600
_MM_SS = re.compile(r"^(\d{1,3}):([0-5]\d)$")


def parse_clock(value: str) -> int:
    """"63:20" or "3800" -> elapsed seconds. Raises ValueError on anything else."""
    value = value.strip()
    if m := _MM_SS.match(value):
        t = int(m[1]) * 60 + int(m[2])
    elif value.isdigit():
        t = int(value)
    else:
        raise ValueError(f"clock {value!r} is not mm:ss or seconds")
    if t > MAX_CLOCK:
        raise ValueError(f"clock {value!r} is past the end of any match")
    return t


def _period_at(match: Match, t: int) -> tuple[int, int]:
    """(period, seconds into it) for elapsed time t, from the periods played so far."""
    started = [p for p in match.periods if p.start_t <= t]
    if not started:
        return 1, t
    return started[-1].period, t - started[-1].start_t


def label_at(match: Match, t: int) -> str:
    return clock_label(*_period_at(match, t))


def score_at(match: Match, events: list[MatchEvent], t: int) -> Score:
    """Score after everything up to t; the stored score once t reaches the current clock."""
    if t >= match.clock:
        return match.score
    goals = [e.team for e in events if e.shot_outcome == "goal" and e.period != 5 and e.t <= t]
    return Score(home=goals.count("home"), away=goals.count("away"))


def build_timeline(match: Match, pivots: list[Pivot], events: list[MatchEvent]) -> OverlayTimeline:
    """One card per confirmed or degraded pivot, appearing at its first trigger event in the pivot minute.

    A card is cut short when the next one appears, so at most one card is ever on screen.
    """
    event_t = {e.event_id: e.t for e in events}
    timed: list[tuple[int, Pivot]] = []
    for p in pivots:
        if p.status not in ("confirmed", "degraded") or p.narrative is None:
            continue
        start = p.minute * 60
        triggers = [event_t[i] for i in p.trigger_event_ids if event_t.get(i, -1) >= start]
        timed.append((min(triggers, default=start), p))
    timed.sort(key=lambda tp: (tp[0], tp[1].minute))

    team_name = {"home": match.home.name, "away": match.away.name}
    cards = []
    for i, (show_at, p) in enumerate(timed):
        hide_at = min(show_at + OVERLAY_CARD_SECONDS, MAX_CLOCK)
        if i + 1 < len(timed):
            hide_at = min(hide_at, timed[i + 1][0])
        if hide_at <= show_at:                # replaced in the same second by a later pivot
            continue
        cards.append(OverlayCard(
            pivot_id=p.pivot_id, minute=p.minute, minute_label=label_at(match, p.minute * 60),
            show_at=show_at, hide_at=hide_at, direction=p.direction, direction_team=team_name[p.direction],
            severity=p.severity, status=p.status, headline=p.narrative.headline,
            subline=p.narrative.sentences[0].text,
        ))
    return OverlayTimeline(match_id=match.match_id, cards=cards)


def frame_at(match: Match, timeline: OverlayTimeline, events: list[MatchEvent], t: int) -> OverlayFrame:
    period, period_t = _period_at(match, t)
    scoreboard = OverlayScoreboard(home_short=match.home.short_name, away_short=match.away.short_name,
                                   score=score_at(match, events, t), period=period,
                                   clock_label=clock_label(period, period_t))
    card = next((c for c in timeline.cards if c.show_at <= t < c.hide_at), None)
    return OverlayFrame(match_id=match.match_id, clock=t, scoreboard=scoreboard, card=card)
