"""The state of the match around a pivot: score, players on the pitch, earlier tactics (Dx9).

The Judge and the Explainer only see a short window of events. Without the score and the
red cards, "the leading side, a man up, drops deep and cedes control" looks like noise, and
a goal that makes it 3-1 can be mistaken for an equaliser.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from pivot_core.domain import MatchEvent, MinuteMetric, TeamTactics

from .scenarios import is_goal, is_red_card

FULL_SIDE = 11
MOMENTUM_SPAN = 10                            # minutes averaged either side of the alarm
# Tactics fields always shown for a coach decision; any other field is shown only when it changed.
TACTIC_FIELDS = ("line_height", "press", "tempo", "width", "counter_attack")
_SKIP = {"set_pieces", "instructions"}


def score_at(events: Iterable[MatchEvent], t: int) -> dict[str, int]:
    """Goals for each side scored at or before elapsed second t (shootout kicks excluded)."""
    goals = [e.team for e in events if is_goal(e) and e.t <= t]
    return {"home": goals.count("home"), "away": goals.count("away")}


def men_at(events: Iterable[MatchEvent], t: int) -> dict[str, int]:
    """Players on the pitch for each side after the red cards (straight or second yellow) up to t."""
    sent_off = [e.team for e in events if is_red_card(e) and e.t <= t]
    return {"home": FULL_SIDE - sent_off.count("home"), "away": FULL_SIDE - sent_off.count("away")}


def score_line(score: Mapping[str, int], team_names: Mapping[str, str]) -> str:
    return f"{team_names['home']} {score['home']}-{score['away']} {team_names['away']}"


def snapshot(events: Sequence[MatchEvent], minute: int, team_names: Mapping[str, str]) -> dict:
    """Score and players on the pitch at the start of `minute` (0-based)."""
    t = max(0, minute) * 60 - 1
    men = men_at(events, t)
    return {"score": score_line(score_at(events, t), team_names),
            "men_on_pitch": {team_names[s]: men[s] for s in ("home", "away")}}


def match_state(minute: int, events: Mapping[str, MatchEvent], team_names: Mapping[str, str], *,
                before: int, after: int, metrics: Sequence[MinuteMetric] = ()) -> dict:
    """Score and players on the pitch before and after the window the model sees, and, given
    metrics, the average momentum over the ten minutes before and after the alarm."""
    evs = list(events.values())
    state = {"before_window": snapshot(evs, minute - before, team_names),
             "after_window": snapshot(evs, minute + after + 1, team_names)}
    if metrics:
        def avg(lo: int, hi: int) -> float | None:
            values = [m.momentum for m in metrics if lo <= m.minute < hi]
            return round(sum(values) / len(values), 3) if values else None
        state["momentum_avg_10_min"] = {"before": avg(minute - MOMENTUM_SPAN, minute),
                                        "after": avg(minute, minute + MOMENTUM_SPAN)}
    return state


def previous_tactics(events: Mapping[str, MatchEvent]) -> dict[str, TeamTactics]:
    """For each event that sets tactics, the tactics its team played with until then."""
    last: dict[str, TeamTactics] = {}
    before: dict[str, TeamTactics] = {}
    for e in sorted(events.values(), key=lambda e: e.seq):
        if e.tactics is None:
            continue
        if e.team in last:
            before[e.event_id] = last[e.team]
        last[e.team] = e.tactics
    return before


def tactics_line(tactics: TeamTactics, previous: TeamTactics | None = None) -> dict:
    """The main tactics fields and anything else that changed, plus the old values of what changed."""
    now = tactics.model_dump(mode="json", exclude=_SKIP)
    old = previous.model_dump(mode="json", exclude=_SKIP) if previous else {}
    changed = [k for k in now if k in old and old[k] != now[k]]
    line = {"tactics": {k: now[k] for k in now if k in TACTIC_FIELDS or k in changed}}
    if changed:
        line["tactics_before"] = {k: old[k] for k in changed}
    return line


def goal_scores(events: Mapping[str, MatchEvent], team_names: Mapping[str, str]) -> dict[str, str]:
    """The score right after each goal, by the goal's event id."""
    evs = list(events.values())
    return {e.event_id: score_line(score_at(evs, e.t), team_names) for e in evs if is_goal(e)}
