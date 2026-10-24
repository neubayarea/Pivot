"""TemplateExplainer: the fallback card when the Explainer cannot pass the Verifier (D05).

It builds up to three sentences from the key events and one recomputed stat change, so
what it writes passes the same Verifier. It must never raise: if anything goes wrong it
returns a minimal card that still fits the Narrative contract.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from pivot_core.domain import ExplanationSentence, MatchEvent, Narrative, PivotCandidate, StatRef, ViewerPrefs
from pivot_core.domain.stats import STAT_UNITS, Claim

from .verifier import EVIDENCE_AFTER, EVIDENCE_BEFORE, StatSource
from .vocabulary import STAT_TERMS, UNIT_SUFFIX

# Stats the template tries, in order of preference when changes are equal.
CANDIDATE_METRICS = ("threat_total", "passes_final_third", "box_entries", "shots", "pressures", "xg")
COMPARE_MINUTES = 5
_DECIMALS = {"count": 0, "pct": 0, "xg": 2, "index": 2, "m": 0, "km": 1}


def format_value(value: float, unit: str) -> str:
    return f"{value:.{_DECIMALS[unit]}f}{UNIT_SUFFIX[unit]}"


def _trigger(event: MatchEvent, team: str) -> tuple[str, str]:
    """Headline and first sentence for the event that set the pivot off."""
    at = event.clock_label
    if event.type == "shot" and event.shot_outcome == "goal":
        return f"{team} goal swings the match", f"{team} scored at {at}."
    if event.type == "card":
        return "A card changes the game", f"{team} were shown a card at {at}."
    if event.type == "substitution":
        return f"{team} change shifts the balance", f"{team} made a substitution at {at}."
    if event.type == "tactical_shift":
        return f"{team} switch shifts the balance", f"{team} changed their shape at {at}."
    if event.type == "injury":
        return "An injury changes the game", f"{team} lost a player to injury at {at}."
    return "", ""


def _stat_sentence(c: PivotCandidate, team: str, stats: StatSource, evidence: list[str]) -> ExplanationSentence | None:
    m = c.minute
    before, after = (max(0, m - COMPARE_MINUTES), m), (m, m + COMPARE_MINUTES)
    best = None
    for metric in CANDIDATE_METRICS:
        try:
            refs = [StatRef(metric=metric, team=c.direction, window=w) for w in (before, after)]
            a, b = (stats.compute(r) for r in refs)
        except Exception:
            continue
        unit = STAT_UNITS[metric]
        if format_value(a, unit) == format_value(b, unit):
            continue
        if best is None or (b - a > 0, abs(b - a) / (abs(a) + 1)) > best[0]:
            best = ((b - a > 0, abs(b - a) / (abs(a) + 1)), metric, refs, a, b)
    if best is None:
        return None
    _, metric, refs, a, b = best
    unit = STAT_UNITS[metric]
    verb = "rose" if b > a else "fell"
    text = (f"{team}'s {STAT_TERMS[metric].label} {verb} from {format_value(a, unit)} "
            f"to {format_value(b, unit)} in the next five minutes.")
    claims = [Claim(value=v, unit=unit, stat_ref=r) for v, r in ((a, refs[0]), (b, refs[1]))]
    return ExplanationSentence(text=text, evidence_ids=evidence, claims=claims)


def _evidence(c: PivotCandidate, events: Mapping[str, MatchEvent]) -> list[MatchEvent]:
    lo, hi = c.minute - EVIDENCE_BEFORE, c.minute + EVIDENCE_AFTER
    keyed = [events[e] for e in c.key_event_ids if e in events and lo <= events[e].minute <= hi]
    if keyed:
        return keyed
    nearby = sorted((e for e in events.values() if lo <= e.minute <= hi), key=lambda e: abs(e.minute - c.minute))
    return nearby[:1]


def clean_headline(text: str) -> str:
    words = re.sub(r"\d", "", text).split()
    return " ".join(words[:8]) or "Momentum swings"


def template_explain(
    candidate: PivotCandidate,
    *,
    events: Mapping[str, MatchEvent],
    stats: StatSource,
    team_names: Mapping[str, str] | None = None,
    prefs: ViewerPrefs | None = None,
    chain_id: str | None = None,
    verifier_attempts: int = 0,
) -> Narrative:
    prefs = prefs or ViewerPrefs()
    names = {"home": "Home", "away": "Away", **(team_names or {})}
    team = names[candidate.direction]
    try:
        found = _evidence(candidate, events)
        ids = [e.event_id for e in found][:4] or [f"{candidate.match_id}:{candidate.minute}"]
        headline, first = _trigger(found[0], names[found[0].team]) if found else ("", "")
        sentences = []
        if first:
            sentences.append(ExplanationSentence(text=first, evidence_ids=ids[:1]))
        stat = _stat_sentence(candidate, team, stats, ids[:4])
        if stat:
            sentences.append(stat)
        sentences.append(ExplanationSentence(text=f"From there the momentum swung towards {team}.", evidence_ids=ids[:4]))
        return Narrative(prefs=prefs, headline=clean_headline(headline or f"Momentum swings to {team}"),
                         sentences=sentences[:3], source="template", verifier_attempts=verifier_attempts,
                         chain_id=chain_id)
    except Exception:
        return Narrative(
            prefs=prefs, headline="Momentum swings",
            sentences=[ExplanationSentence(text="The match turned around this point.",
                                           evidence_ids=list(candidate.key_event_ids[:1]) or [candidate.match_id])],
            source="template", verifier_attempts=verifier_attempts, chain_id=chain_id,
        )
