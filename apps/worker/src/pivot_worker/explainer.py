"""Explainer prompt, output schema and request building (D04).

The model never computes numbers: the request carries a stat sheet of recomputed values
(one `Claim` per metric, team and window) and the model copies the ones it uses. That keeps
the Verifier's number check a formality and the first-pass rate high (ADR-0005).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Annotated

from pydantic import Field

from pivot_core.domain import ExplanationSentence, MatchEvent, Narrative, PivotCandidate, StatRef, Verdict, ViewerPrefs
from pivot_core.domain.common import Model
from pivot_core.domain.stats import STAT_UNITS, Claim

from .context import ContextItem, relevant
from .languages import INSTRUCTIONS
from .prompts import Prompt, render
from .template import possessive
from .verifier import EVIDENCE_AFTER, EVIDENCE_BEFORE, StatSource
from .vocabulary import BANNED_TERMS, DOWN_WORDS, JARGON, SIGNIFICANCE_WORDS, UP_WORDS, vocabulary_markdown

COMPARE_MINUTES = 5
MAX_EVENTS = 30
# Event types always worth showing the model, in the order it should notice them.
KEY_TYPES = ("shot", "card", "substitution", "tactical_shift", "injury", "foul", "save")
# Player-level stats offered in focus-player mode.
PLAYER_METRICS = ("passes", "pass_accuracy_pct", "passes_final_third", "shots", "xg", "duels_won", "tackles_won",
                  "turnovers", "distance_covered_km")
# The versions written for every pivot by default: one per audience.
DEFAULT_VERSIONS = (ViewerPrefs(audience="analyst"), ViewerPrefs(audience="fan"))


class ExplainerDraft(Model):
    """What the model returns. Turned into a `Narrative` once it parses."""

    headline: Annotated[str, Field(max_length=80)]
    sentences: Annotated[list[ExplanationSentence], Field(min_length=1, max_length=3)]


def audience_brief(prefs: ViewerPrefs, team_names: Mapping[str, str],
                   player_names: Mapping[str, str] | None = None) -> str:
    """The "Reader" section of a system prompt (FR-23, FR-24)."""
    lines = []
    if prefs.audience == "fan":
        lines.append(
            "A fan watching the match, not an analyst. Tell it as a short story: who did what, and how it "
            "changed the game. Use everyday words and the fan wording from the stat table. Never use "
            f"abbreviations or tactics jargon ({', '.join(JARGON)}). Use at most one number per sentence, "
            "and only if it makes the story clearer.")
    else:
        lines.append(
            "A match analyst. Be precise and tactical: name the mechanism (shape, pressing, space, "
            "overloads) and back each step with a stat from the sheet. Use the analyst labels from the table.")
    if prefs.focus_team:
        lines.append(f"Tell it from {possessive(team_names[prefs.focus_team])} point of view: what they gained or lost here, "
                     "even when the match turned against them.")
    if prefs.focus_player_id:
        name = (player_names or {}).get(prefs.focus_player_id, prefs.focus_player_id)
        lines.append(f"The viewer follows {name} (`{prefs.focus_player_id}`). Mention them when the evidence "
                     "involves them, and prefer their player-level stats from the sheet; never invent a role "
                     "for them in events they were not part of.")
    lines.append(INSTRUCTIONS[prefs.language])
    return " ".join(lines)


def stat_sheet(candidate: PivotCandidate, stats: StatSource, *, player_id: str | None = None,
               player_team: str | None = None) -> list[Claim]:
    """Every metric for both teams, five minutes before and after the pivot, plus the focus player's."""
    m = candidate.minute
    windows = ((max(0, m - COMPARE_MINUTES), m), (m, m + COMPARE_MINUTES))
    refs = [StatRef(metric=metric, team=team, window=w)
            for metric in STAT_UNITS for team in ("home", "away") for w in windows]
    if player_id and player_team:
        refs += [StatRef(metric=metric, team=player_team, window=w, player_id=player_id)
                 for metric in PLAYER_METRICS for w in windows]
    sheet = []
    for ref in refs:
        try:
            sheet.append(Claim(value=round(stats.compute(ref), 3), unit=STAT_UNITS[ref.metric], stat_ref=ref))
        except Exception:
            continue
    return sheet


def window_events(candidate: PivotCandidate, events: Mapping[str, MatchEvent], *,
                  before: int = EVIDENCE_BEFORE, after: int = EVIDENCE_AFTER) -> list[MatchEvent]:
    """Events the model may cite: key events first, then the notable ones, capped."""
    lo, hi = candidate.minute - before, candidate.minute + after
    in_window = [e for e in events.values() if lo <= e.minute <= hi]
    keys = set(candidate.key_event_ids)

    def rank(e: MatchEvent) -> tuple:
        kind = KEY_TYPES.index(e.type) if e.type in KEY_TYPES else len(KEY_TYPES)
        return (e.event_id not in keys, kind, -abs(e.threat))

    chosen = sorted(in_window, key=rank)[:MAX_EVENTS]
    return sorted(chosen, key=lambda e: e.seq)


def event_line(e: MatchEvent, team_names: Mapping[str, str], player_names: Mapping[str, str] | None = None) -> dict:
    line = {"id": e.event_id, "clock": e.clock_label, "type": e.type, "team": team_names[e.team]}
    if player_names and e.player_id in player_names:
        line["player"] = player_names[e.player_id]
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


FAN_EXAMPLE = ExplainerDraft(
    headline="Okafor changes the game for Rovers",
    sentences=[ExplanationSentence(
        text="Okafor came on at 61' and suddenly Rovers kept finding a way into Harbour's half.",
        evidence_ids=["m063-s01042", "m063-s01077"],
    ), ExplanationSentence(
        text="Their passes into the attacking third rose from 3 to 9 in five minutes, and Harbour were hanging on.",
        evidence_ids=["m063-s01077"],
        claims=[
            Claim(value=3, unit="count", stat_ref=StatRef(metric="passes_final_third", team="home", window=(56, 61))),
            Claim(value=9, unit="count", stat_ref=StatRef(metric="passes_final_third", team="home", window=(61, 66))),
        ],
    )],
)


def system_prompt(prefs: ViewerPrefs, team_names: Mapping[str, str],
                  player_names: Mapping[str, str] | None = None) -> Prompt:
    shots = (EXAMPLES[0], FAN_EXAMPLE) if prefs.audience == "fan" else EXAMPLES
    examples = "\n\n".join(f"```json\n{ex.model_dump_json(indent=1)}\n```" for ex in shots)
    return render(
        "explainer",
        audience=audience_brief(prefs, team_names, player_names),
        schema=json.dumps(ExplainerDraft.model_json_schema()),
        direction_words=", ".join(UP_WORDS + DOWN_WORDS),
        significance_words=", ".join(SIGNIFICANCE_WORDS),
        banned_terms=", ".join(BANNED_TERMS),
        vocabulary=vocabulary_markdown(prefs.audience),
        examples=examples,
    )


def _player_team(player_id: str | None, events: Mapping[str, MatchEvent]) -> str | None:
    return next((e.team for e in events.values() if player_id and e.player_id == player_id), None)


def build_request(
    candidate: PivotCandidate,
    *,
    events: Mapping[str, MatchEvent],
    stats: StatSource,
    team_names: Mapping[str, str],
    prefs: ViewerPrefs | None = None,
    player_names: Mapping[str, str] | None = None,
    context: Sequence[ContextItem] = (),
    feedback: Verdict | None = None,
) -> str:
    focus = (prefs or ViewerPrefs()).focus_player_id
    shown = window_events(candidate, events)
    request = {
        "pivot": {"minute": candidate.minute, "clock": f"{candidate.minute + 1}'",
                  "towards": team_names[candidate.direction], "swing": round(candidate.swing, 3),
                  "key_event_ids": candidate.key_event_ids},
        "teams": dict(team_names),
        "events": [event_line(e, team_names, player_names) for e in shown],
        "stat_sheet": [c.model_dump() for c in stat_sheet(candidate, stats, player_id=focus,
                                                          player_team=_player_team(focus, events))],
    }
    if context:
        request["match_context"] = [{"id": i.context_id, "about": list(i.subject_ids), "note": i.text}
                                    for i in relevant(context, shown)]
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
    player_names: Mapping[str, str] | None = None,
    context: Sequence[ContextItem] = (),
    feedback: Verdict | None = None,
) -> tuple[Prompt, list[dict[str, str]]]:
    """System and user messages for one Explainer call, plus the prompt (for its hash)."""
    prefs = prefs or ViewerPrefs()
    prompt = system_prompt(prefs, team_names, player_names)
    user = build_request(candidate, events=events, stats=stats, team_names=team_names, prefs=prefs,
                         player_names=player_names, context=context, feedback=feedback)
    return prompt, [{"role": "system", "content": prompt.text}, {"role": "user", "content": user}]


def parse_draft(raw: str | dict, *, prefs: ViewerPrefs | None = None, chain_id: str | None = None,
                verifier_attempts: int = 0) -> Narrative:
    """Validate the model output. Raises pydantic.ValidationError, which counts as `schema_invalid`."""
    draft = ExplainerDraft.model_validate_json(raw) if isinstance(raw, str) else ExplainerDraft.model_validate(raw)
    return Narrative(prefs=prefs or ViewerPrefs(), headline=draft.headline, sentences=draft.sentences,
                     source="llm", verifier_attempts=verifier_attempts, chain_id=chain_id)
