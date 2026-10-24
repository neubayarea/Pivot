"""Deterministic Verifier for explanations (D05, ADR-0005, architecture §6.3).

The Verifier never calls a model. It recomputes every claim through a `StatSource`
(B05's StatCalculator in production, a fake in tests) and checks six kinds of rule:

1. shape: sentence count, words per sentence, evidence count, headline length and digits
2. evidence: every evidence id exists and falls from 8 minutes before the pivot to 5 after
3. numbers: every claim recomputes within tolerance, and every number in the text has a claim
4. direction: rose/fell words match the sign of the change between two claimed windows
5. significance: "significant"-style words only when the what-if intervals do not overlap
6. wording: no banned terms

Issue messages are written for the Explainer, which gets them back on a retry.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Protocol

from pivot_core.domain import MatchEvent, Narrative, StatRef, Verdict, VerifierIssue
from pivot_core.domain.stats import Claim

from .vocabulary import BANNED_TERMS, DOWN_WORDS, SIGNIFICANCE_WORDS, UP_WORDS

MAX_WORDS = 30
MAX_HEADLINE_WORDS = 8
EVIDENCE_BEFORE, EVIDENCE_AFTER = 8, 5

# Allowed gap between a claimed value and the recomputed one, per unit.
TOLERANCE = {"count": 0.0, "pct": 0.5, "xg": 0.01, "index": 0.02, "m": 0.5, "km": 0.05, "ratio": 0.05}

# Numbers in running text. Match minutes ("61'", "45+2'") are not claims and are skipped.
_MINUTE = re.compile(r"\b\d{1,3}(?:\+\d{1,2})?['’′]")
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


class StatSource(Protocol):
    def compute(self, ref: StatRef) -> float: ...


def numbers_in(text: str) -> list[str]:
    return _NUMBER.findall(_MINUTE.sub(" ", text))


def _matches(number: str, claim: Claim) -> bool:
    """True if a number as written could be the claim's value (allowing for rounding)."""
    decimals = len(number.split(".")[1]) if "." in number else 0
    slack = max(TOLERANCE[claim.unit], 0.5 * 10**-decimals)
    return abs(float(number) - claim.value) <= slack + 1e-9


def _has_word(text: str, words: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    found = []
    for w in words:
        pattern = re.escape(w.lower()) if not w[0].isalnum() or not w[-1].isalnum() else rf"\b{re.escape(w.lower())}\b"
        if re.search(pattern, lowered):
            found.append(w)
    return found


def _deltas(claims: list[Claim], stats: StatSource) -> list[float]:
    """Changes between claims on the same stat in two different windows, earlier to later."""
    by_stat: dict[tuple, list[Claim]] = {}
    for c in claims:
        key = (c.stat_ref.metric, c.stat_ref.team, c.stat_ref.player_id)
        by_stat.setdefault(key, []).append(c)
    deltas = []
    for group in by_stat.values():
        group = sorted(group, key=lambda c: c.stat_ref.window)
        for a, b in zip(group, group[1:]):
            if a.stat_ref.window != b.stat_ref.window:
                deltas.append(stats.compute(b.stat_ref) - stats.compute(a.stat_ref))
    return deltas


def verify(
    narrative: Narrative,
    *,
    pivot_minute: int,
    events: Mapping[str, MatchEvent],
    stats: StatSource,
    significant: Mapping[str, bool] | None = None,
    max_sentences: int = 3,
) -> Verdict:
    """Check a pivot card (or, with `significant`, a what-if comparison) against the data."""
    issues: list[VerifierIssue] = []

    def issue(code: str, message: str, index: int | None = None) -> None:
        issues.append(VerifierIssue(code=code, message=message, sentence_index=index))

    # 1. Shape.
    if not 1 <= len(narrative.sentences) <= max_sentences:
        issue("sentence_count", f"Write 1 to {max_sentences} sentences, not {len(narrative.sentences)}.")
    if len(narrative.headline.split()) > MAX_HEADLINE_WORDS:
        issue("too_long", f"The headline must be at most {MAX_HEADLINE_WORDS} words.")
    if re.search(r"\d", narrative.headline):
        issue("number_mismatch", "The headline must not contain digits.")
    for term in _has_word(narrative.headline, BANNED_TERMS):
        issue("banned_term", f"Remove '{term}' from the headline.")

    lo, hi = pivot_minute - EVIDENCE_BEFORE, pivot_minute + EVIDENCE_AFTER
    allow_significance = bool(significant) and any(significant.values())

    for i, s in enumerate(narrative.sentences):
        words = len(s.text.split())
        if words > MAX_WORDS:
            issue("too_long", f"Sentence {i + 1} has {words} words; keep it to {MAX_WORDS}.", i)
        if not 1 <= len(s.evidence_ids) <= 4:
            issue("evidence_count", f"Sentence {i + 1} must cite 1 to 4 evidence ids.", i)

        # 2. Evidence.
        for eid in s.evidence_ids:
            event = events.get(eid)
            if event is None:
                issue("evidence_invalid", f"Evidence {eid} does not exist.", i)
            elif not lo <= event.minute <= hi:
                issue("evidence_invalid", f"Evidence {eid} is at minute {event.minute}, outside {lo}-{hi}.", i)

        # 3. Numbers: claims recompute, and the text carries no unclaimed numbers.
        for c in s.claims:
            actual = stats.compute(c.stat_ref)
            if abs(c.value - actual) > TOLERANCE[c.unit] + 1e-9:
                ref = c.stat_ref
                issue("number_mismatch",
                      f"{ref.metric} for {ref.team} in {ref.window[0]}-{ref.window[1]} is {actual:g}, not {c.value:g}.", i)
        for n in numbers_in(s.text):
            if not any(_matches(n, c) for c in s.claims):
                issue("number_mismatch", f"The number {n} in sentence {i + 1} has no matching claim.", i)

        # 4. Direction words.
        up, down = _has_word(s.text, UP_WORDS), _has_word(s.text, DOWN_WORDS)
        if up or down:
            deltas = _deltas(list(s.claims), stats)
            if not deltas:
                issue("direction_mismatch",
                      f"'{(up or down)[0]}' needs two claims on the same stat in different windows.", i)
            else:
                if up and not any(d > 0 for d in deltas):
                    issue("direction_mismatch", f"'{up[0]}' says it went up, but the numbers did not rise.", i)
                if down and not any(d < 0 for d in deltas):
                    issue("direction_mismatch", f"'{down[0]}' says it went down, but the numbers did not fall.", i)

        # 5. Significance wording.
        if not allow_significance:
            for w in _has_word(s.text, SIGNIFICANCE_WORDS):
                issue("significance_unsupported", f"Do not say '{w}': the difference is not significant.", i)

        # 6. Banned terms.
        for term in _has_word(s.text, BANNED_TERMS):
            issue("banned_term", f"Remove '{term}' from sentence {i + 1}.", i)

    return Verdict(passed=not issues, issues=issues)
