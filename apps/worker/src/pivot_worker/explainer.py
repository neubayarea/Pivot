"""Explainer prompt, output schema and request building (D04).

The model never computes numbers: the request carries a stat sheet of recomputed values
(one `Claim` per metric, team and window) and the model copies the ones it uses. That keeps
the Verifier's number check a formality and the first-pass rate high (ADR-0005).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Annotated

from pydantic import Field

from pivot_core.domain import ExplanationSentence, MatchEvent, Narrative, PivotCandidate, StatRef, Verdict, ViewerPrefs
from pivot_core.domain.common import Model
from pivot_core.domain.stats import STAT_UNITS, Claim

from .prompts import Prompt, render
from .verifier import EVIDENCE_AFTER, EVIDENCE_BEFORE, StatSource
from .vocabulary import BANNED_TERMS, DOWN_WORDS, SIGNIFICANCE_WORDS, UP_WORDS, vocabulary_markdown

COMPARE_MINUTES = 5
MAX_EVENTS = 30
# Event types always worth showing the model, in the order it should notice them.
KEY_TYPES = ("shot", "card", "substitution", "tactical_shift", "injury", "foul", "save")


class ExplainerDraft(Model):
    """What the model returns. Turned into a `Narrative` once it parses."""

    headline: Annotated[str, Field(max_length=80)]
    sentences: Annotated[list[ExplanationSentence], Field(min_length=1, max_length=3)]


def audience_brief(prefs: ViewerPrefs, team_names: Mapping[str, str]) -> str:
    lines = []
    if prefs.audience == "fan":
        lines.append("A fan watching the match. Tell it as a story, in everyday words, with no abbreviations "
                     "or tactical jargon. Use the fan wording from the stat table.")
    else:
        lines.append("An analyst. Be precise and tactical; use the stat labels from the table.")
    if prefs.focus_team:
        lines.append(f"Tell it from {team_names[prefs.focus_team]}'s point of view.")
    if prefs.focus_player_id:
        lines.append(f"Mention player `{prefs.focus_player_id}` where the evidence involves them.")
    lines.append("Write in English.")
    return " ".join(lines)


def stat_sheet(candidate: PivotCandidate, stats: StatSource) -> list[Claim]:
    """Every metric for both teams, five minutes before and after the pivot."""
    m = candidate.minute
    windows = ((max(0, m - COMPARE_MINUTES), m), (m, m + COMPARE_MINUTES))
    sheet = []
    for metric, unit in STAT_UNITS.items():
        for team in ("home", "away"):
            for w in windows:
                ref = StatRef(metric=metric, team=team, window=w)
                try:
                    sheet.append(Claim(value=round(stats.compute(ref), 3), unit=unit, stat_ref=ref))
                except Exception:
                    continue
    return sheet


def window_events(candidate: PivotCandidate, events: Mapping[str, MatchEvent]) -> list[MatchEvent]:
    """Events the model may cite: key events first, then the notable ones, capped."""
    lo, hi = candidate.minute - EVIDENCE_BEFORE, candidate.minute + EVIDENCE_AFTER
    in_window = [e for e in events.values() if lo <= e.minute <= hi]
    keys = set(candidate.key_event_ids)

    def rank(e: MatchEvent) -> tuple:
        kind = KEY_TYPES.index(e.type) if e.type in KEY_TYPES else len(KEY_TYPES)
        return (e.event_id not in keys, kind, -abs(e.threat))

    chosen = sorted(in_window, key=rank)[:MAX_EVENTS]
    return sorted(chosen, key=lambda e: e.seq)


def _event_line(e: MatchEvent, team_names: Mapping[str, str]) -> dict:
    line = {"id": e.event_id, "clock": e.clock_label, "type": e.type, "team": team_names[e.team]}
    for key in ("player_id", "receiver_id", "outcome", "shot_outcome", "xg"):
        if (value := getattr(e, key)) is not None:
            line[key] = value
    if e.substitution:
        line["substitution"] = e.substitution.model_dump(exclude_defaults=True)
    return line


EXAMPLES = (
    ExplainerDraft(
        headline="Okafor's arrival flips the left flank",
        sentences=[ExplanationSentence(
            text="Okafor came on at 61' and Rovers' final-third passes rose from 3 to 9 in the next five minutes.",
            evidence_ids=["m063-s01042", "m063-s01077"],
            claims=[
                Claim(value=3, unit="count", stat_ref=StatRef(metric="passes_final_third", team="home", window=(56, 61))),
                Claim(value=9, unit="count", stat_ref=StatRef(metric="passes_final_third", team="home", window=(61, 66))),
            ],
        ), ExplanationSentence(
            text="Harbour's press could not reach him, and Rovers started living in their half.",
            evidence_ids=["m063-s01077"],
        )],
    ),
    ExplainerDraft(
        headline="The red card pins Harbour back",
        sentences=[ExplanationSentence(
            text="After the red card at 36' Harbour's defensive line dropped from 41 m to 33 m.",
            evidence_ids=["m038-s00811"],
            claims=[
                Claim(value=41, unit="m", stat_ref=StatRef(metric="line_height_m", team="away", window=(31, 36))),
                Claim(value=33, unit="m", stat_ref=StatRef(metric="line_height_m", team="away", window=(36, 41))),
            ],
        ), ExplanationSentence(
            text="That invited Rovers forward, and the chances began to come.",
            evidence_ids=["m038-s00840", "m038-s00866"],
        )],
    ),
)


def system_prompt(prefs: ViewerPrefs, team_names: Mapping[str, str]) -> Prompt:
    examples = "\n\n".join(f"```json\n{ex.model_dump_json(indent=1)}\n```" for ex in EXAMPLES)
    return render(
        "explainer",
        audience=audience_brief(prefs, team_names),
        schema=json.dumps(ExplainerDraft.model_json_schema()),
        direction_words=", ".join(UP_WORDS + DOWN_WORDS),
        significance_words=", ".join(SIGNIFICANCE_WORDS),
        banned_terms=", ".join(BANNED_TERMS),
        vocabulary=vocabulary_markdown(prefs.audience),
        examples=examples,
    )


def build_request(
    candidate: PivotCandidate,
    *,
    events: Mapping[str, MatchEvent],
    stats: StatSource,
    team_names: Mapping[str, str],
    feedback: Verdict | None = None,
) -> str:
    request = {
        "pivot": {"minute": candidate.minute, "clock": f"{candidate.minute + 1}'",
                  "towards": team_names[candidate.direction], "swing": round(candidate.swing, 3),
                  "key_event_ids": candidate.key_event_ids},
        "teams": dict(team_names),
        "events": [_event_line(e, team_names) for e in window_events(candidate, events)],
        "stat_sheet": [c.model_dump() for c in stat_sheet(candidate, stats)],
    }
    text = json.dumps(request, ensure_ascii=False)
    if feedback and not feedback.passed:
        fixes = "\n".join(f"- {i.code}: {i.message}" for i in feedback.issues)
        text += f"\n\nThe Verifier rejected your previous card:\n{fixes}"
    return text


def build_messages(
    candidate: PivotCandidate,
    *,
    events: Mapping[str, MatchEvent],
    stats: StatSource,
    team_names: Mapping[str, str],
    prefs: ViewerPrefs | None = None,
    feedback: Verdict | None = None,
) -> tuple[Prompt, list[dict[str, str]]]:
    """System and user messages for one Explainer call, plus the prompt (for its hash)."""
    prompt = system_prompt(prefs or ViewerPrefs(), team_names)
    user = build_request(candidate, events=events, stats=stats, team_names=team_names, feedback=feedback)
    return prompt, [{"role": "system", "content": prompt.text}, {"role": "user", "content": user}]


def parse_draft(raw: str | dict, *, prefs: ViewerPrefs | None = None, chain_id: str | None = None,
                verifier_attempts: int = 0) -> Narrative:
    """Validate the model output. Raises pydantic.ValidationError, which counts as `schema_invalid`."""
    draft = ExplainerDraft.model_validate_json(raw) if isinstance(raw, str) else ExplainerDraft.model_validate(raw)
    return Narrative(prefs=prefs or ViewerPrefs(), headline=draft.headline, sentences=draft.sentences,
                     source="llm", verifier_attempts=verifier_attempts, chain_id=chain_id)
