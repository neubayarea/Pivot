"""TemplateExplainer: the fallback card when the Explainer cannot pass the Verifier (D05).

It builds up to three sentences from the key events and one recomputed stat change, so
what it writes passes the same Verifier. With a focus team it tells the story from their side,
even when the match turned against them; fan versions write only the newer value of the change.
It must never raise: if anything goes wrong it returns a minimal card that still fits the
Narrative contract.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from pivot_core.domain import ExplanationSentence, MatchEvent, Narrative, PivotCandidate, StatRef, ViewerPrefs
from pivot_core.domain.stats import STAT_UNITS, Claim

from .context import ContextItem, involved_in
from .languages import LABELS, MAX_HEADLINE, PHRASES
from .verifier import EVIDENCE_AFTER, EVIDENCE_BEFORE, StatSource
from .vocabulary import STAT_TERMS, UNIT_SUFFIX

# Stats the template tries, in order of preference when changes are equal.
CANDIDATE_METRICS = ("threat_total", "passes_final_third", "box_entries", "shots", "pressures", "xg")
# Fan wording that reads as a noun after "Rovers'"; xG is left out because its unit is jargon.
FAN_METRICS = ("threat_total", "passes_final_third", "shots")
COMPARE_MINUTES = 5
_DECIMALS = {"count": 0, "pct": 0, "xg": 2, "index": 2, "m": 0, "km": 1, "ratio": 1}


def format_value(value: float, unit: str) -> str:
    return f"{value:.{_DECIMALS[unit]}f}{UNIT_SUFFIX[unit]}"


def _trigger(event: MatchEvent, team: str, lang: str = "en") -> tuple[str, str]:
    """Headline and first sentence for the event that set the pivot off."""
    kind = "goal" if event.type == "shot" and event.shot_outcome == "goal" else event.type
    phrases = PHRASES[lang]
    if kind not in ("goal", "card", "substitution", "tactical_shift", "injury"):
        return "", ""
    return (phrases[f"{kind}_h"].format(team=team),
            phrases[kind].format(team=team, at=event.clock_label))


def _label(metric: str, lang: str, fan: bool) -> str:
    if lang in LABELS:
        return LABELS[lang][metric]
    term = STAT_TERMS[metric]
    return term.fan_label if fan else term.label


def _stat_sentence(c: PivotCandidate, side: str, team: str, stats: StatSource, evidence: list[str],
                   fan: bool = False, lang: str = "en") -> ExplanationSentence | None:
    """The biggest change for `side`: a rise if the match turned their way, a fall if it turned against them."""
    m = c.minute
    before, after = (max(0, m - COMPARE_MINUTES), m), (m, m + COMPARE_MINUTES)
    gaining = side == c.direction
    best = None
    for metric in FAN_METRICS if fan else CANDIDATE_METRICS:
        try:
            refs = [StatRef(metric=metric, team=side, window=w) for w in (before, after)]
            a, b = (stats.compute(r) for r in refs)
        except Exception:
            continue
        unit = STAT_UNITS[metric]
        if format_value(a, unit) == format_value(b, unit):
            continue
        score = ((b - a > 0) == gaining, abs(b - a) / (abs(a) + 1))
        if best is None or score > best[0]:
            best = (score, metric, refs, a, b)
    if best is None:
        return None
    _, metric, refs, a, b = best
    unit = STAT_UNITS[metric]
    phrases = PHRASES[lang]
    text = phrases["stat_fan" if fan else "stat"].format(
        team=team, owner=possessive(team), label=_label(metric, lang, fan), verb=phrases["rose" if b > a else "fell"],
        a=format_value(a, unit), b=format_value(b, unit))
    if lang == "es":
        text = text[0].upper() + text[1:]
    claims = [Claim(value=v, unit=unit, stat_ref=r) for v, r in ((a, refs[0]), (b, refs[1]))]
    return ExplanationSentence(text=text, evidence_ids=evidence, claims=claims)


def _evidence(c: PivotCandidate, events: Mapping[str, MatchEvent]) -> list[MatchEvent]:
    lo, hi = c.minute - EVIDENCE_BEFORE, c.minute + EVIDENCE_AFTER
    keyed = [events[e] for e in c.key_event_ids if e in events and lo <= events[e].minute <= hi]
    if keyed:
        return keyed
    nearby = sorted((e for e in events.values() if lo <= e.minute <= hi), key=lambda e: abs(e.minute - c.minute))
    return nearby[:1]


def _context_sentence(trigger: MatchEvent, context: Sequence[ContextItem],
                      evidence: list[str]) -> ExplanationSentence | None:
    """Cite the first context item about someone in the trigger event, if it reads cleanly."""
    people = involved_in(trigger)
    for item in context:
        text = f"Off the pitch: {item.text}."
        if people & set(item.subject_ids) and not re.search(r"\d", item.text) and len(text.split()) <= 30:
            return ExplanationSentence(text=text, evidence_ids=evidence, context_ids=[item.context_id])
    return None


def possessive(name: str) -> str:
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def clean_headline(text: str, lang: str = "en") -> str:
    """No digits, and cut to the language's headline limit."""
    text = re.sub(r"\d", "", text).strip()
    limit = MAX_HEADLINE[lang]
    if lang == "zh":
        return text[:limit] or PHRASES["zh"]["fallback_h"]
    return " ".join(text.split()[:limit]) or PHRASES[lang]["fallback_h"]


def template_explain(
    candidate: PivotCandidate,
    *,
    events: Mapping[str, MatchEvent],
    stats: StatSource,
    team_names: Mapping[str, str] | None = None,
    prefs: ViewerPrefs | None = None,
    chain_id: str | None = None,
    verifier_attempts: int = 0,
    context: Sequence[ContextItem] = (),
) -> Narrative:
    prefs = prefs or ViewerPrefs()
    lang = prefs.language
    names = {"home": "Home", "away": "Away", **(team_names or {})}
    side = prefs.focus_team or candidate.direction
    team = names[side]
    gaining = side == candidate.direction
    try:
        phrases = PHRASES[lang]
        found = _evidence(candidate, events)
        ids = [e.event_id for e in found][:4] or [f"{candidate.match_id}:{candidate.minute}"]
        headline, first = _trigger(found[0], names[found[0].team], lang) if found else ("", "")
        sentences = []
        if first:
            sentences.append(ExplanationSentence(text=first, evidence_ids=ids[:1]))
        note = _context_sentence(found[0], context, ids[:1]) if found and lang == "en" else None
        if note:
            sentences.append(note)
        stat = _stat_sentence(candidate, side, team, stats, ids[:4], fan=prefs.audience == "fan", lang=lang)
        if stat:
            sentences.append(stat)
        momentum = "momentum" if gaining else "momentum_lost"
        sentences.append(ExplanationSentence(text=phrases[momentum].format(team=team), evidence_ids=ids[:4]))
        fallback_headline = phrases[f"{momentum}_h"].format(team=team)
        return Narrative(prefs=prefs, headline=clean_headline(headline or fallback_headline, lang),
                         sentences=sentences[:3], source="template", verifier_attempts=verifier_attempts,
                         chain_id=chain_id)
    except Exception:
        phrases = PHRASES.get(lang, PHRASES["en"])
        return Narrative(
            prefs=prefs, headline=phrases["fallback_h"],
            sentences=[ExplanationSentence(text=phrases["fallback"],
                                           evidence_ids=list(candidate.key_event_ids[:1]) or [candidate.match_id])],
            source="template", verifier_attempts=verifier_attempts, chain_id=chain_id,
        )
