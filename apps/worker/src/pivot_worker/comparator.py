"""Comparator: explains why the what-if group ended differently from the baseline (D07).

Outcome probabilities are not stat-vocabulary metrics, so a comparison carries no claims and
no numbers; the S3 chart shows the recomputed distribution. The Verifier instead checks that
each "more likely" style word matches the change of the outcome it describes, and that
significance words only appear about outcomes whose intervals do not overlap (`significant`
from the SimResult). The replays are a simulation, so the wording never goes past that.

`compare` is the entry point once a scenario has finished: Comparator ⇄ Verifier, then the
template if no draft passes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

from pydantic import ValidationError

from pivot_core.domain import (
    ExplanationSentence,
    MatchEvent,
    Narrative,
    SimResult,
    StatRef,
    Verdict,
    VerifierIssue,
    ViewerPrefs,
)

from .explainer import KEY_TYPES, ExplainerDraft, audience_brief, parse_draft
from .models import ModelClient, ModelUnavailable
from .pipeline import Step, StepRecorder
from .prompts import Prompt, render
from .template import clean_headline
from .verifier import EVIDENCE_AFTER, EVIDENCE_BEFORE, OutcomeMention, StatSource, verify
from .vocabulary import BANNED_TERMS, SIGNIFICANCE_WORDS

OUTCOMES = ("home_win", "draw", "away_win")
MAX_CHECKS = 3                                # first draft plus two rewrites, as for pivot cards
COMPARATOR_TIMEOUT = 8.0
MAX_CITABLE = 5

EXAMPLE = ExplainerDraft(
    headline="Keeping Moreau on protects the lead",
    sentences=[
        ExplanationSentence(text="With Moreau still on the left, a Harbour City win became more likely in the replays.",
                            evidence_ids=["m063-s02302"]),
        ExplanationSentence(text="Northvale Rovers no longer found the space behind the full-back that the change had opened.",
                            evidence_ids=["m063-s02302"]),
    ],
)


def outcome_names(team_names: Mapping[str, str]) -> dict[str, tuple[str, ...]]:
    """Phrases that name each outcome in a sentence."""
    home, away = team_names["home"], team_names["away"]
    return {
        "home_win": (f"{home} win", f"{home} victory", "home win"),
        "away_win": (f"{away} win", f"{away} victory", "away win"),
        "draw": ("draw",),
        "home_advance": (f"{home} go through", f"{home} going through", f"{away} go out"),
    }


def changes(result: SimResult) -> dict[str, float]:
    keys = OUTCOMES + (("home_advance",) if result.baseline.home_advance is not None else ())
    return {k: (getattr(result.counterfactual, k) or 0) - (getattr(result.baseline, k) or 0) for k in keys}


def outcome_mentions(result: SimResult, team_names: Mapping[str, str]):
    """For the Verifier: every outcome a sentence names, where, and how it changed."""
    deltas, names = changes(result), outcome_names(team_names)

    def mentioned(text: str) -> list[OutcomeMention]:
        lowered, found = text.lower(), {}
        for k, phrases in names.items():
            if k not in deltas:
                continue
            for p in phrases:
                for m in re.finditer(rf"\b{re.escape(p.lower())}\b", lowered):
                    found.setdefault(m.start(), OutcomeMention(text[m.start():m.end()], m.start(), m.end(), deltas[k],
                                                               bool(result.significant.get(k))))
        return sorted(found.values(), key=lambda m: m.start)

    return mentioned


def citable_events(target_event_id: str | None, at_minute: int, events: Mapping[str, MatchEvent]) -> list[str]:
    """Evidence a comparison may cite: the event the scenario changed, wherever it is.

    A tactical change (change_press) has no such event, so the events nearest the minute it
    starts from are offered instead, key events first.
    """
    if target_event_id:
        return [target_event_id]
    lo, hi = at_minute - EVIDENCE_BEFORE, at_minute + EVIDENCE_AFTER
    near = [e for e in events.values() if lo <= e.minute <= hi]

    def rank(e: MatchEvent) -> tuple:
        return (abs(e.minute - at_minute), KEY_TYPES.index(e.type) if e.type in KEY_TYPES else len(KEY_TYPES), e.seq)

    return [e.event_id for e in sorted(near, key=rank)[:MAX_CITABLE]]


def system_prompt(result: SimResult, prefs: ViewerPrefs, team_names: Mapping[str, str]) -> Prompt:
    if any(result.significant.values()):
        rule = (f"You may use {', '.join(SIGNIFICANCE_WORDS)} only about these outcomes, whose intervals do not "
                f"overlap: {', '.join(k for k, v in result.significant.items() if v)}.")
    else:
        rule = (f"No interval separates the groups: say the difference is within noise, and never use "
                f"{', '.join(SIGNIFICANCE_WORDS)}.")
    return render("comparator", audience=audience_brief(prefs, team_names),
                  schema=json.dumps(ExplainerDraft.model_json_schema()), significance_rule=rule,
                  banned_terms=", ".join(BANNED_TERMS), example=EXAMPLE.model_dump_json(indent=1))


def build_messages(result: SimResult, *, scenario_label: str, target_event_id: str | None, at_minute: int,
                   team_names: Mapping[str, str], events: Mapping[str, MatchEvent] | None = None,
                   prefs: ViewerPrefs | None = None,
                   feedback: Verdict | None = None) -> tuple[Prompt, list[dict[str, str]]]:
    request = {
        "scenario": scenario_label, "changed_event_id": target_event_id, "from_clock": f"{at_minute + 1}'",
        "evidence_ids": citable_events(target_event_id, at_minute, events or {}),
        "teams": dict(team_names),
        "baseline": result.baseline.model_dump(), "with_change": result.counterfactual.model_dump(),
        "change": {k: round(v, 3) for k, v in changes(result).items()},
        "significant": result.significant,
    }
    text = json.dumps(request, ensure_ascii=False)
    if feedback and not feedback.passed:
        text += "\n\nThe Verifier rejected your previous comparison:\n" + "\n".join(
            f"- {i.code}: {i.message}" for i in feedback.issues)
    prompt = system_prompt(result, prefs or ViewerPrefs(), team_names)
    return prompt, [{"role": "system", "content": prompt.text}, {"role": "user", "content": text}]


def verify_comparison(narrative: Narrative, result: SimResult, *, at_minute: int, events: Mapping[str, MatchEvent],
                      stats: StatSource, team_names: Mapping[str, str], target_event_id: str | None) -> Verdict:
    return verify(narrative, pivot_minute=at_minute, events=events, stats=stats, significant=result.significant,
                  outcomes=outcome_mentions(result, team_names),
                  allowed_evidence=citable_events(target_event_id, at_minute, events))


def _phrase(outcome: str, team_names: Mapping[str, str]) -> str:
    return "a draw" if outcome == "draw" else f"a {team_names[outcome.split('_')[0]]} win"


def template_comparison(result: SimResult, *, evidence_id: str, team_names: Mapping[str, str],
                        prefs: ViewerPrefs | None = None, chain_id: str | None = None,
                        verifier_attempts: int = 0) -> Narrative:
    """Fallback that names a change only when its intervals do not overlap, and says it is a replay."""
    deltas = changes(result)
    clear = [o for o in OUTCOMES if result.significant.get(o) and abs(deltas[o]) > 1e-9]
    if clear:
        k = max(clear, key=lambda o: abs(deltas[o]))
        phrase, word = _phrase(k, team_names), "more likely" if deltas[k] > 0 else "less likely"
        headline = f"Replays: {phrase[2:]} {word}"
        first = f"With the change, {phrase} became {word} in the replays."
        second = "The two intervals do not overlap, so this is more than noise."
    else:
        headline = "Replays show no clear difference"
        first = "The replays with the change show no clear difference from the ones without it."
        second = "The two intervals overlap for every result, so any gap is within noise."
    return Narrative(prefs=prefs or ViewerPrefs(), headline=clean_headline(headline),
                     sentences=[ExplanationSentence(text=first, evidence_ids=[evidence_id]),
                                ExplanationSentence(text=second, evidence_ids=[evidence_id])],
                     source="template", verifier_attempts=verifier_attempts, chain_id=chain_id)


class _NoClaims:
    """Comparisons carry no claims, so nothing is ever recomputed."""

    def compute(self, ref: StatRef) -> float:
        raise LookupError("comparisons carry no claims")


async def _skip(step: Step) -> None:
    return None


async def compare(result: SimResult, *, scenario_label: str, target_event_id: str | None, at_minute: int,
                  events: Mapping[str, MatchEvent], team_names: Mapping[str, str], models: ModelClient,
                  record: StepRecorder | None = None, prefs: ViewerPrefs | None = None,
                  chain_id: str | None = None) -> Narrative:
    """Comparator ⇄ Verifier for a finished scenario, falling back to the template. Never raises.

    The result goes in `SimResult.narrative`. `record` gets one Step per agent call, like the
    Detect chain, so the caller can store them as AgentTraces.
    """
    record, prefs = record or _skip, prefs or ViewerPrefs()
    feedback, checks = None, 0
    while checks < MAX_CHECKS:
        prompt, messages = build_messages(result, scenario_label=scenario_label, target_event_id=target_event_id,
                                          at_minute=at_minute, team_names=team_names, events=events, prefs=prefs,
                                          feedback=feedback)
        try:
            reply = await models.complete_json("standard", messages, timeout=COMPARATOR_TIMEOUT)
        except ModelUnavailable as e:
            await record(Step("comparator", f"unavailable: {e}"[:200], "error", prompt_hash=prompt.hash))
            break
        checks += 1
        try:
            draft = parse_draft(reply.text, prefs=prefs, chain_id=chain_id, verifier_attempts=checks)
        except ValidationError as e:
            draft = None
            verdict = Verdict(passed=False, issues=[VerifierIssue(
                code="schema_invalid", message=f"{e.error_count()} schema errors: {e.errors()[0]['msg']}")])
        else:
            verdict = verify_comparison(draft, result, at_minute=at_minute, events=events, stats=_NoClaims(),
                                        team_names=team_names, target_event_id=target_event_id)
        await record(Step("comparator", draft.headline if draft else "invalid output",
                          "retried" if checks > 1 else "ok", reply.model, prompt.hash, reply.tokens))
        await record(Step("verifier", "pass" if verdict.passed else "; ".join(i.code for i in verdict.issues),
                          "ok" if verdict.passed else "rejected", verdict=verdict))
        if verdict.passed:
            return draft
        feedback = verdict
    evidence = (citable_events(target_event_id, at_minute, events) or list(events) or ["none"])[0]
    narrative = template_comparison(result, evidence_id=evidence, team_names=team_names, prefs=prefs,
                                    chain_id=chain_id, verifier_attempts=checks)
    await record(Step("template", narrative.headline, "degraded"))
    return narrative
