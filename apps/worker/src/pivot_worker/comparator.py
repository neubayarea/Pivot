"""Comparator: explains why the what-if group ended differently from the baseline (D07).

Outcome probabilities are not stat-vocabulary metrics, so a comparison carries no claims and
no numbers; the S3 chart shows the recomputed distribution. The Verifier instead checks that
"more likely" style words match the outcome changes and that significance words only appear
when the intervals do not overlap (`significant` from the SimResult).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

from pivot_core.domain import ExplanationSentence, MatchEvent, Narrative, SimResult, Verdict, ViewerPrefs

from .explainer import ExplainerDraft, audience_brief
from .prompts import Prompt, render
from .template import clean_headline
from .verifier import StatSource, verify
from .vocabulary import BANNED_TERMS, SIGNIFICANCE_WORDS

OUTCOMES = ("home_win", "draw", "away_win")

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


def outcome_deltas(result: SimResult, team_names: Mapping[str, str]):
    deltas, names = changes(result), outcome_names(team_names)

    def mentioned(text: str) -> list[float]:
        lowered = text.lower()
        return [deltas[k] for k, phrases in names.items()
                if k in deltas and any(re.search(rf"\b{re.escape(p.lower())}\b", lowered) for p in phrases)]

    return mentioned


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
                   team_names: Mapping[str, str], prefs: ViewerPrefs | None = None,
                   feedback: Verdict | None = None) -> tuple[Prompt, list[dict[str, str]]]:
    request = {
        "scenario": scenario_label, "changed_event_id": target_event_id, "from_clock": f"{at_minute + 1}'",
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
                      stats: StatSource, team_names: Mapping[str, str]) -> Verdict:
    return verify(narrative, pivot_minute=at_minute, events=events, stats=stats, significant=result.significant,
                  outcome_deltas=outcome_deltas(result, team_names), team_names=team_names)


def _phrase(outcome: str, team_names: Mapping[str, str]) -> str:
    return "a draw" if outcome == "draw" else f"a {team_names[outcome.split('_')[0]]} win"


def template_comparison(result: SimResult, *, evidence_id: str, team_names: Mapping[str, str],
                        prefs: ViewerPrefs | None = None, chain_id: str | None = None,
                        verifier_attempts: int = 0) -> Narrative:
    """Fallback that only states the direction of the biggest change and whether it is noise."""
    deltas = changes(result)
    k = max(OUTCOMES, key=lambda o: abs(deltas[o]))
    phrase = _phrase(k, team_names)
    if abs(deltas[k]) < 1e-9:
        first = "The change made no difference to the results in the replays."
        headline = "The change makes no difference"
    else:
        word = "more likely" if deltas[k] > 0 else "less likely"
        first = f"With the change, {phrase} became {word} in the replays."
        headline = f"{phrase[2].upper()}{phrase[3:]} becomes {word}"
    second = ("The two intervals do not overlap, so this is more than noise." if result.significant.get(k)
              else "The two intervals overlap, so the difference is within noise.")
    return Narrative(prefs=prefs or ViewerPrefs(), headline=clean_headline(headline),
                     sentences=[ExplanationSentence(text=first, evidence_ids=[evidence_id]),
                                ExplanationSentence(text=second, evidence_ids=[evidence_id])],
                     source="template", verifier_attempts=verifier_attempts, chain_id=chain_id)
