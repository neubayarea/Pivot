"""PivotJudge prompt, output schema and the deterministic fallback (D03).

The Judge runs on the mini model with a 4 second timeout (architecture §6.2). When it times
out or keeps failing, `fallback_verdict` marks the pivot from the detector alone and the
workflow sets the status to "degraded".
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Annotated, Literal

from pydantic import Field

from pivot_core.domain import MatchEvent, MinuteMetric, Pivot, PivotCandidate
from pivot_core.domain.common import Model
from pivot_core.domain.pivots import PivotStatus

from .explainer import event_line, stat_sheet, window_events
from .prompts import Prompt, render
from .verifier import StatSource

JUDGE_WINDOW = 8                              # minutes either side of the alarm
JUDGE_METRICS = ("possession_pct", "threat_total", "shots", "xg", "passes_final_third", "pressures", "turnovers")


class JudgeVerdict(Model):
    is_pivot: bool
    severity: Literal[1, 2, 3]
    trigger_event_ids: Annotated[list[str], Field(max_length=3)]
    reason: Annotated[str, Field(max_length=200)]


EXAMPLES = (
    ("Alarm at 63' towards Rovers. Okafor came on at 61'; Rovers' threat and final-third passes "
     "tripled in the next five minutes and momentum stayed with them for eight minutes.",
     JudgeVerdict(is_pivot=True, severity=2, trigger_event_ids=["m063-s01042"],
                  reason="The substitution opened the left flank and Rovers kept control afterwards.")),
    ("Alarm at 27' towards Harbour. One long Harbour possession ended in a blocked shot; "
     "momentum returned to level within two minutes and no substitution, card or change of shape happened.",
     JudgeVerdict(is_pivot=False, severity=1, trigger_event_ids=[],
                  reason="A single spell of pressure that faded at once, with nothing on the pitch behind it.")),
)


def system_prompt() -> Prompt:
    examples = "\n\n".join(f"{situation}\n\n```json\n{v.model_dump_json()}\n```" for situation, v in EXAMPLES)
    return render("judge", schema=json.dumps(JudgeVerdict.model_json_schema()), examples=examples)


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
        "alarm": {"minute": candidate.minute, "clock": f"{candidate.minute + 1}'",
                  "towards": team_names[candidate.direction], "cusum": round(candidate.cusum_stat, 3),
                  "swing": round(candidate.swing, 3), "key_event_ids": candidate.key_event_ids},
        "teams": dict(team_names),
        "momentum_by_minute": [{"minute": m.minute, "momentum": round(m.momentum, 3)}
                               for m in metrics if lo <= m.minute <= hi],
        "events": [event_line(e, team_names)
                   for e in window_events(candidate, events, before=JUDGE_WINDOW, after=JUDGE_WINDOW)],
        "stats": [c.model_dump() for c in stat_sheet(candidate, stats) if c.stat_ref.metric in JUDGE_METRICS],
    }
    prompt = system_prompt()
    return prompt, [{"role": "system", "content": prompt.text},
                    {"role": "user", "content": json.dumps(request, ensure_ascii=False)}]


def parse_verdict(raw: str | dict, candidate: PivotCandidate, known_ids: set[str]) -> JudgeVerdict:
    """Validate the model output and drop trigger ids it made up.

    Raises pydantic.ValidationError on a bad shape. A "yes" whose triggers were all invented
    falls back to the detector's key events, so a confirmed pivot always points at something real.
    """
    v = JudgeVerdict.model_validate_json(raw) if isinstance(raw, str) else JudgeVerdict.model_validate(raw)
    triggers = [i for i in v.trigger_event_ids if i in known_ids]
    if v.is_pivot and not triggers:
        triggers = candidate.key_event_ids[:3]
    return v.model_copy(update={"trigger_event_ids": triggers if v.is_pivot else []})


def fallback_verdict(candidate: PivotCandidate) -> JudgeVerdict:
    """Detector-only verdict for when the Judge is unavailable."""
    swing = abs(candidate.swing)
    severity = 3 if swing >= 0.5 else 2 if swing >= 0.3 else 1
    return JudgeVerdict(is_pivot=True, severity=severity, trigger_event_ids=candidate.key_event_ids[:3],
                        reason="Judge unavailable; marked from the momentum detector alone.")


def make_pivot(candidate: PivotCandidate, verdict: JudgeVerdict, *, chain_id: str, status: PivotStatus) -> Pivot:
    return Pivot(pivot_id=f"{candidate.match_id}:p{candidate.minute}", match_id=candidate.match_id,
                 minute=candidate.minute, direction=candidate.direction, severity=verdict.severity,
                 status=status, trigger_event_ids=verdict.trigger_event_ids, chain_id=chain_id)
