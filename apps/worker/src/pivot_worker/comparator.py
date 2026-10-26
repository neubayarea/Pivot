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
    label_at,
    period_starts,
)

from .explainer import KEY_TYPES, ExplainerDraft, audience_brief, parse_draft
from .languages import COMPARISON, has_cjk
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


def outcome_names(team_names: Mapping[str, str], lang: str = "en") -> dict[str, tuple[str, ...]]:
    """Phrases that name each outcome in a sentence; English ones are accepted in every language."""
    home, away = team_names["home"], team_names["away"]
    names = {
        "home_win": [f"{home} win", f"{home} victory", "home win"],
        "away_win": [f"{away} win", f"{away} victory", "away win"],
        "draw": ["draw"],
        "home_advance": [f"{home} go through", f"{home} going through", f"{away} go out"],
    }
    if lang == "zh":
        for k, team, side in (("home_win", home, "主"), ("away_win", away, "客")):
            names[k] += [f"{team}获胜", f"{team}取胜", f"{team}赢球", f"{team}胜出", f"{side}队获胜", f"{side}胜"]
        names["draw"] += ["平局", "战平", "打平", "握手言和"]
        names["home_advance"] += [f"{home}晋级", f"{away}出局", f"{away}被淘汰"]
    elif lang == "es":
        for k, team, side in (("home_win", home, "local"), ("away_win", away, "visitante")):
            names[k] += [f"victoria de {team}", f"victoria del {team}", f"triunfo de {team}", f"gane {team}",
                         f"{team} gane", f"victoria {side}"]
        names["draw"] += ["empate"]
        names["home_advance"] += [f"{home} pase", f"{home} se clasifique", f"clasificación de {home}",
                                  f"{away} quede eliminado"]
    return {k: tuple(v) for k, v in names.items()}


def changes(result: SimResult) -> dict[str, float]:
    keys = OUTCOMES + (("home_advance",) if result.baseline.home_advance is not None else ())
    return {k: (getattr(result.counterfactual, k) or 0) - (getattr(result.baseline, k) or 0) for k in keys}


def _spans(text: str, phrase: str):
    """Where a phrase occurs in lower-cased text; Chinese has no word boundaries."""
    pattern = re.escape(phrase.lower()) if has_cjk(phrase) else rf"\b{re.escape(phrase.lower())}\b"
    return re.finditer(pattern, text)


# A team named before "more likely to win" names its win: "Harbour City were more likely to win",
# "Harbour City更有可能获胜". The team's name is where the outcome is.
_LIKELY_TO_WIN = {
    "en": r"(?=[^.;:,]{0,30}?\b(?:more likely|less likely|likelier) to win\b)",
    "zh": r"(?=[^。；，,]{0,6}?(?:更有可能|可能性更大|可能性更小|更不可能)(?:获胜|取胜|赢球|胜出))",
}


def outcome_mentions(result: SimResult, team_names: Mapping[str, str], lang: str = "en"):
    """For the Verifier: every outcome a sentence names, where, and how it changed."""
    deltas, names = changes(result), outcome_names(team_names, lang)
    likely = [p for p in (_LIKELY_TO_WIN["en"], _LIKELY_TO_WIN.get(lang)) if p]
    teams = [(f"{side}_win", team_names[side]) for side in ("home", "away")]

    def mentioned(text: str) -> list[OutcomeMention]:
        lowered, found = text.lower(), {}

        def add(k: str, m: re.Match) -> None:
            found.setdefault(m.start(), OutcomeMention(text[m.start():m.end()], m.start(), m.end(), deltas[k],
                                                       bool(result.significant.get(k))))
        for k, phrases in names.items():
            if k not in deltas:
                continue
            for p in phrases:
                for m in _spans(lowered, p):
                    add(k, m)
        for k, team in teams:
            for pattern in likely:
                for m in re.finditer(rf"(?<![a-z0-9]){re.escape(team.lower())}(?![a-z0-9]){pattern}", lowered):
                    add(k, m)
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
    from_clock = label_at(period_starts((events or {}).values()), at_minute * 60)
    request = {
        "scenario": scenario_label, "changed_event_id": target_event_id, "from_clock": from_clock,
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
                      team_names: Mapping[str, str], target_event_id: str | None,
                      stats: StatSource | None = None) -> Verdict:
    """The Verifier on a comparison; `stats` only matters if it carries claims, which a comparison never does."""
    return verify(narrative, pivot_minute=at_minute, events=events, stats=stats or _NoClaims(),
                  significant=result.significant,
                  outcomes=outcome_mentions(result, team_names, narrative.prefs.language),
                  allowed_evidence=citable_events(target_event_id, at_minute, events), team_names=team_names)


def _phrase(outcome: str, team_names: Mapping[str, str], lang: str = "en", key: str = "win") -> str:
    phrases = COMPARISON[lang]
    if outcome == "draw":
        return phrases[key.replace("win", "draw")]
    return phrases[key].format(team=team_names[outcome.split("_")[0]])


def template_comparison(result: SimResult, *, evidence_id: str, team_names: Mapping[str, str],
                        prefs: ViewerPrefs | None = None, chain_id: str | None = None,
                        verifier_attempts: int = 0) -> Narrative:
    """Fallback that names a change only when its intervals do not overlap, and says it is a replay."""
    prefs = prefs or ViewerPrefs()
    lang = prefs.language
    phrases = COMPARISON[lang]
    deltas = changes(result)
    clear = [o for o in OUTCOMES if result.significant.get(o) and abs(deltas[o]) > 1e-9]
    if clear:
        k = max(clear, key=lambda o: abs(deltas[o]))
        word = phrases["more" if deltas[k] > 0 else "less"]
        first = phrases["first"].format(outcome=_phrase(k, team_names, lang), word=word)
        headline = phrases["first_h"].format(outcome=_phrase(k, team_names, lang, "win_h"), word=word)
        second = phrases["apart"]
    else:
        first, headline, second = phrases["none"], phrases["none_h"], phrases["noise"]
    return Narrative(prefs=prefs, headline=clean_headline(headline, lang),
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
