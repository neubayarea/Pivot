"""PivotJudge prompt, output schema and the deterministic fallback (D03).

The Judge runs on the mini model with a 4 second timeout (architecture §6.2). When it times
out or keeps failing, `fallback_verdict` marks the pivot from the detector alone and the
workflow sets the status to "degraded".
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
from typing import Annotated, Literal

from pydantic import Field

from pivot_core.domain import MatchEvent, MinuteMetric, Pivot, PivotCandidate, StatRef, label_at, period_starts
from pivot_core.domain.common import Model
from pivot_core.domain.pivots import PivotStatus
from pivot_core.domain.stats import STAT_UNITS, Claim

from .explainer import event_lines, stat_sheet, window_events
from .matchstate import match_state
from .prompts import Prompt, render
from .verifier import StatSource

MAX_TRIGGERS = 3
JUDGE_WINDOW = 8                              # minutes either side of the alarm
JUDGE_METRICS = ("possession_pct", "threat_total", "shots", "xg", "passes_final_third", "pressures", "turnovers")


class JudgeVerdict(Model):
    is_pivot: bool
    severity: Literal[1, 2, 3]
    trigger_event_ids: Annotated[list[str], Field(max_length=MAX_TRIGGERS)]
    reason: Annotated[str, Field(max_length=200)]


class InvalidVerdict(ValueError):
    """A "yes" that names no real trigger: treated like a Judge failure, so the pivot is degraded."""


def _momentum(start: int, values: Sequence[float]) -> list[dict]:
    return [{"minute": start + i, "momentum": v} for i, v in enumerate(values)]


def _stat(metric: str, team: str, window: tuple[int, int], value: float) -> dict:
    ref = StatRef(metric=metric, team=team, window=window)
    return Claim(value=value, unit=STAT_UNITS[metric], stat_ref=ref).model_dump(mode="json")


def momentum_sign(team_names: Mapping[str, str]) -> str:
    return f"above 0: {team_names['home']} on top; below 0: {team_names['away']} on top"


_TEAMS = {"home": "Rovers", "away": "Harbour"}


def _state(before: str, after: str, men_before=(11, 11), men_after=(11, 11), avg=(0.0, 0.0)) -> dict:
    def snap(score: str, men: tuple[int, int]) -> dict:
        return {"score": score, "men_on_pitch": dict(zip(_TEAMS.values(), men))}
    return {"before_window": snap(before, men_before), "after_window": snap(after, men_after),
            "momentum_avg_10_min": {"before": avg[0], "after": avg[1]}}


# Each example is a request exactly as `build_messages` sends it (events and stats trimmed)
# and the verdict for it. Windows match the real ones: momentum and events 8 minutes either
# side of the alarm, stats 5 minutes before and after it, match state around the window.
# Momentum, swing, CUSUM value and the 10-minute averages are real readings of the Opta-style
# series (MET-024) with the B06 detector, moved onto the examples' minutes (sign flipped where
# the example's home side is the demo's away side): the demo match's p79 (substitution),
# p37 (red card) and p66 (leading side drops deep), and seed 1125's 28' alarm, a four-minute
# spike with nothing behind it (scripts/momentum_tune.py's 200 demo-preset matches).
EXAMPLES = (
    ({"alarm": {"minute": 62, "clock": "63'", "towards": "Rovers", "cusum": 1.42, "swing": 0.33,
                "key_event_ids": ["m063-s01042"]},
      "teams": _TEAMS, "momentum_sign": momentum_sign(_TEAMS),
      "match_state": _state("Rovers 0-1 Harbour", "Rovers 0-1 Harbour", avg=(-0.08, 0.2)),
      "momentum_by_minute": _momentum(54, [0.08, -0.22, -0.38, -0.15, -0.03, -0.15, -0.07, -0.1, 0.19,
                                           0.13, 0.03, 0.34, 0.45, 0.08, 0.09, 0.18, 0.15]),
      "events": [{"id": "m063-s01042", "clock": "61'", "type": "substitution", "team": "Rovers",
                  "player_id": "R-17", "substitution": {"player_off_id": "R-11", "player_on_id": "R-17"}},
                 {"id": "m063-s01077", "clock": "63'", "type": "pass", "team": "Rovers", "player_id": "R-17",
                  "receiver_id": "R-9", "outcome": "success"},
                 {"id": "m063-s01120", "clock": "65'", "type": "shot", "team": "Rovers", "player_id": "R-9",
                  "shot_outcome": "saved", "xg": 0.31}],
      "stats": [_stat("threat_total", "home", (57, 62), 0.19), _stat("threat_total", "home", (62, 67), 0.58),
                _stat("passes_final_third", "home", (57, 62), 3), _stat("passes_final_third", "home", (62, 67), 9)]},
     JudgeVerdict(is_pivot=True, severity=2, trigger_event_ids=["m063-s01042"],
                  reason="The substitution opened the left flank and Rovers kept control for eight minutes.")),
    ({"alarm": {"minute": 39, "clock": "40'", "towards": "Harbour", "cusum": 1.41, "swing": -0.47,
                "key_event_ids": ["m063-s00811"]},
      "teams": _TEAMS, "momentum_sign": momentum_sign(_TEAMS),
      "match_state": _state("Rovers 0-0 Harbour", "Rovers 0-0 Harbour", men_after=(10, 11), avg=(-0.02, -0.29)),
      "momentum_by_minute": _momentum(31, [-0.08, -0.03, -0.02, 0.09, 0.04, 0.15, 0.19, -0.04, -0.23,
                                           -0.44, -0.65, -0.41, -0.19, -0.29, -0.15, -0.25, -0.16]),
      "events": [{"id": "m063-s00811", "clock": "38'", "type": "card", "team": "Rovers", "player_id": "R-4"},
                 {"id": "m063-s00840", "clock": "41'", "type": "shot", "team": "Harbour", "player_id": "H-10",
                  "shot_outcome": "off_target", "xg": 0.08}],
      "stats": [_stat("shots", "away", (34, 39), 0), _stat("shots", "away", (39, 44), 3),
                _stat("possession_pct", "home", (34, 39), 58.0),
                _stat("possession_pct", "home", (39, 44), 36.0)]},
     JudgeVerdict(is_pivot=True, severity=3, trigger_event_ids=["m063-s00811"],
                  reason="After the Rovers card momentum went below zero and stayed there, with Harbour shooting at will.")),
    ({"alarm": {"minute": 26, "clock": "27'", "towards": "Harbour", "cusum": 1.42, "swing": -0.47,
                "key_event_ids": []},
      "teams": _TEAMS, "momentum_sign": momentum_sign(_TEAMS),
      "match_state": _state("Rovers 1-1 Harbour", "Rovers 1-1 Harbour", avg=(-0.03, -0.2)),
      "momentum_by_minute": _momentum(18, [-0.19, -0.12, -0.07, 0.29, 0.13, 0.03, 0.15, -0.06, -0.19,
                                           -0.47, -0.44, -0.4, -0.28, -0.12, 0.1, 0.04, -0.2]),
      "events": [{"id": "m063-s00512", "clock": "27'", "type": "shot", "team": "Harbour", "player_id": "H-9",
                  "shot_outcome": "blocked", "xg": 0.06}],
      "stats": [_stat("shots", "away", (21, 26), 0), _stat("shots", "away", (26, 31), 1),
                _stat("possession_pct", "home", (21, 26), 52.0),
                _stat("possession_pct", "home", (26, 31), 49.0)]},
     JudgeVerdict(is_pivot=False, severity=1, trigger_event_ids=[],
                  reason="A four-minute spell of Harbour pressure that faded straight after, with nothing on the pitch behind it.")),
    ({"alarm": {"minute": 72, "clock": "73'", "towards": "Harbour", "cusum": 1.94, "swing": -0.35,
                "key_event_ids": ["m063-s01502", "m063-s01503"]},
      "teams": _TEAMS, "momentum_sign": momentum_sign(_TEAMS),
      "match_state": _state("Rovers 2-1 Harbour", "Rovers 2-1 Harbour", avg=(0.33, 0.02)),
      "momentum_by_minute": _momentum(64, [0.05, -0.04, 0.35, 0.59, 0.49, 0.58, 0.59, 0.36, 0.22, 0.29,
                                           0.14, 0.11, 0.1, 0.08, -0.22, -0.38, -0.15]),
      "events": [{"id": "m063-s01502", "clock": "71'", "type": "substitution", "team": "Rovers", "player_id": "R-14",
                  "substitution": {"player_off_id": "R-8", "player_on_id": "R-14", "slot": 8, "reason": "tactical"}},
                 {"id": "m063-s01503", "clock": "71'", "type": "tactical_shift", "team": "Rovers",
                  "tactics": {"line_height": "low", "press": "low", "width": "normal", "tempo": "slow",
                              "counter_attack": True},
                  "tactics_before": {"line_height": "mid", "press": "high", "tempo": "normal",
                                     "counter_attack": False}},
                 {"id": "m063-s01561", "clock": "75'", "type": "shot", "team": "Harbour", "player_id": "H-9",
                  "shot_outcome": "saved", "xg": 0.14}],
      "stats": [_stat("possession_pct", "home", (67, 72), 55.0), _stat("possession_pct", "home", (72, 77), 38.0),
                _stat("threat_total", "away", (67, 72), 0.07), _stat("threat_total", "away", (72, 77), 0.29)]},
     JudgeVerdict(is_pivot=True, severity=2, trigger_event_ids=["m063-s01503", "m063-s01502"],
                  reason="Leading Rovers dropped deep and stopped pressing; Harbour took over the ball and momentum "
                         "stayed lower.")),
)


def system_prompt() -> Prompt:
    examples = "\n\n".join(f"Request:\n\n```json\n{json.dumps(request, ensure_ascii=False)}\n```\n\n"
                            f"Answer:\n\n```json\n{v.model_dump_json()}\n```" for request, v in EXAMPLES)
    return render("judge", schema=json.dumps(JudgeVerdict.model_json_schema()), examples=examples)


def judge_events(candidate: PivotCandidate, events: Mapping[str, MatchEvent]) -> list[MatchEvent]:
    """The events the Judge is shown, and so the only ones it may name as triggers."""
    return window_events(candidate, events, before=JUDGE_WINDOW, after=JUDGE_WINDOW)


def build_messages(
    candidate: PivotCandidate,
    *,
    events: Mapping[str, MatchEvent],
    metrics: Sequence[MinuteMetric],
    stats: StatSource,
    team_names: Mapping[str, str],
) -> tuple[Prompt, list[dict[str, str]]]:
    lo, hi = candidate.minute - JUDGE_WINDOW, candidate.minute + JUDGE_WINDOW
    request = {
        "alarm": {"minute": candidate.minute, "clock": label_at(period_starts(events.values()), candidate.minute * 60),
                  "towards": team_names[candidate.direction], "cusum": round(candidate.cusum_stat, 3),
                  "swing": round(candidate.swing, 3), "key_event_ids": candidate.key_event_ids},
        "teams": dict(team_names),
        "momentum_sign": momentum_sign(team_names),
        "momentum_by_minute": [{"minute": m.minute, "momentum": round(m.momentum, 3)}
                               for m in metrics if lo <= m.minute <= hi],
        "match_state": match_state(candidate.minute, events, team_names, before=JUDGE_WINDOW, after=JUDGE_WINDOW,
                                   metrics=metrics),
        "events": event_lines(judge_events(candidate, events), events, team_names),
        "stats": [c.model_dump() for c in stat_sheet(candidate, stats) if c.stat_ref.metric in JUDGE_METRICS],
    }
    prompt = system_prompt()
    return prompt, [{"role": "system", "content": prompt.text},
                    {"role": "user", "content": json.dumps(request, ensure_ascii=False)}]


def parse_verdict(raw: str | dict, candidate: PivotCandidate, known_ids: Collection[str]) -> JudgeVerdict:
    """Validate the model output and drop trigger ids it made up.

    `known_ids` are the ids of the events the Judge was shown (`judge_events`), not the whole
    match. Raises pydantic.ValidationError on a bad shape, and InvalidVerdict on a "yes" with
    no real trigger left, so a confirmed pivot always points at something the Judge saw. More
    than three ids is not a bad shape: the first three real ones are kept.
    """
    data = json.loads(raw) if isinstance(raw, str) else dict(raw)
    if isinstance(data, dict) and isinstance(ids := data.get("trigger_event_ids"), list):
        real = [i for i in ids if i in known_ids]
        data["trigger_event_ids"] = (real or ids)[:MAX_TRIGGERS]
    v = JudgeVerdict.model_validate(data)
    if not v.is_pivot:
        return v.model_copy(update={"trigger_event_ids": []})
    triggers = [i for i in v.trigger_event_ids if i in known_ids]
    if not triggers:
        raise InvalidVerdict(f"no real trigger among {v.trigger_event_ids}")
    return v.model_copy(update={"trigger_event_ids": triggers})


def fallback_verdict(candidate: PivotCandidate) -> JudgeVerdict:
    """Detector-only verdict for when the Judge is unavailable."""
    swing = abs(candidate.swing)
    severity = 3 if swing >= 0.33 else 2 if swing >= 0.2 else 1    # Opta-style momentum (MET-024): 0.65 x the old cut-offs
    return JudgeVerdict(is_pivot=True, severity=severity, trigger_event_ids=candidate.key_event_ids[:3],
                        reason="Judge unavailable; marked from the momentum detector alone.")


def make_pivot(candidate: PivotCandidate, verdict: JudgeVerdict, *, chain_id: str, status: PivotStatus) -> Pivot:
    return Pivot(pivot_id=f"{candidate.match_id}:p{candidate.minute}", match_id=candidate.match_id,
                 minute=candidate.minute, direction=candidate.direction, severity=verdict.severity,
                 status=status, trigger_event_ids=verdict.trigger_event_ids, chain_id=chain_id)
