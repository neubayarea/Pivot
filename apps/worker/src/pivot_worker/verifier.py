"""Deterministic Verifier for explanations (D05, ADR-0005, architecture §6.3).

The Verifier never calls a model. It recomputes every claim through a `StatSource`
(B05's StatCalculator in production, a fake in tests) and checks six kinds of rule:

1. shape: sentence count, words per sentence, evidence count, headline length and digits
2. evidence: every evidence id exists and falls from 8 minutes before the pivot to 5 after
   (comparisons instead cite only the ids they were offered)
3. numbers: every claim recomputes within tolerance, and every number in the text has a claim
4. direction: rose/fell words match the sign of the change between two claimed windows; in
   comparisons, "more likely" style words match the outcome they describe
5. significance: "significant"-style words only about outcomes whose what-if intervals do not overlap
6. wording: no banned terms, and no jargon in fan versions
7. context: every `context_ids` entry is a real item of the match context (D13)

Issue messages are written for the Explainer, which gets them back on a retry.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Mapping
from typing import NamedTuple, Protocol

from pivot_core.domain import MatchEvent, Narrative, StatRef, Verdict, VerifierIssue
from pivot_core.domain.stats import Claim

from . import languages as lang_rules
from .vocabulary import JARGON

EVIDENCE_BEFORE, EVIDENCE_AFTER = 8, 5

# Allowed gap between a claimed value and the recomputed one, per unit.
TOLERANCE = {"count": 0.0, "pct": 0.5, "xg": 0.01, "index": 0.02, "m": 0.5, "km": 0.05, "ratio": 0.05}

# Numbers in running text. Match minutes ("61'", "45+2'", "第61分钟") are not claims and are
# skipped. A digit right after a Chinese character still counts ("从3上升到9").
_NUMBER = re.compile(r"(?<![A-Za-z\d.])\d+(?:\.\d+)?")


# Words that point a likelihood word at a second outcome: "a win became more likely than a draw",
# "más probable que un empate", and in Chinese "平局比主队获胜更有可能" (the marker comes first).
_THAN_AFTER = re.compile(r"\s*(?:than|que)\b", re.IGNORECASE)
_THAN_BEFORE = "比"


class StatSource(Protocol):
    def compute(self, ref: StatRef) -> float: ...


class OutcomeMention(NamedTuple):
    """One outcome named in a comparison sentence, where it is, and how it changed."""

    outcome: str
    start: int
    end: int
    delta: float
    significant: bool


def _compute(stats: StatSource, ref: StatRef) -> float | None:
    """Recompute a stat; None if the source cannot (missing data, or no StatCalculator yet)."""
    try:
        return stats.compute(ref)
    except Exception:
        return None


def numbers_in(text: str, lang: str = "en") -> list[str]:
    return _NUMBER.findall(lang_rules.MINUTES.sub(" ", lang_rules.normalise(text, lang)))


def _matches(number: str, claim: Claim) -> bool:
    """True if a number as written could be the claim's value (allowing for rounding)."""
    decimals = len(number.split(".")[1]) if "." in number else 0
    slack = max(TOLERANCE[claim.unit], 0.5 * 10**-decimals)
    return abs(float(number) - claim.value) <= slack + 1e-9


def _pattern(w: str) -> str:
    if lang_rules.has_cjk(w) or not w[0].isalnum() or not w[-1].isalnum():   # no word boundaries in Chinese
        return re.escape(w.lower())
    return rf"\b{re.escape(w.lower())}\b"


def _spans(text: str, words: tuple[str, ...]) -> list[tuple[int, int, str]]:
    lowered = text.lower()
    return sorted((m.start(), m.end(), w) for w in words for m in re.finditer(_pattern(w), lowered))


def _has_word(text: str, words: tuple[str, ...]) -> list[str]:
    found = {w for *_, w in _spans(text, words)}
    return [w for w in words if w in found]


def _outcome_directions(text: str, mentions: list[OutcomeMention], up: tuple[str, ...],
                        down: tuple[str, ...]) -> list[str]:
    """Check each direction word against the outcome it describes, not any outcome in the sentence.

    The outcome is the nearest one named before the word in its clause (or the first one after
    it); "X more likely than Y" also needs X to have gained on Y. Returns problems for the writer.
    """
    words = sorted([(a, b, w, 1) for a, b, w in _spans(text, up)] + [(a, b, w, -1) for a, b, w in _spans(text, down)])
    problems, clause_start = [], 0
    for a, b, word, sign in words:
        before = [m for m in mentions if clause_start <= m.start and m.end <= a]
        after = [m for m in mentions if m.start >= b]
        marker = text.rfind(_THAN_BEFORE, clause_start, a)
        clause_start = b
        other = None
        if marker >= 0 and any(m.end <= marker for m in before):
            subject = [m for m in before if m.end <= marker][-1]
            other = next((m for m in before if m.start > marker), None)
        elif before:
            subject = before[-1]
            other = after[0] if after and _THAN_AFTER.match(text, b) else None
        elif after:
            subject = after[0]
        else:
            problems.append(f"'{word}' must name the result it is about (for example 'a draw').")
            continue
        went = "more" if subject.delta > 0 else "less" if subject.delta < 0 else "no more or less"
        if sign * subject.delta <= 0:
            problems.append(f"'{word}' is about {subject.outcome}, which became {went} likely in the replays.")
        elif other is not None and sign * (subject.delta - other.delta) <= 0:
            problems.append(f"'{word}' compares {subject.outcome} with {other.outcome}, but {subject.outcome} "
                            f"did not {'gain on' if sign > 0 else 'lose ground to'} it.")
    return problems


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
            va, vb = _compute(stats, a.stat_ref), _compute(stats, b.stat_ref)
            if a.stat_ref.window != b.stat_ref.window and va is not None and vb is not None:
                deltas.append(vb - va)
    return deltas


def verify(
    narrative: Narrative,
    *,
    pivot_minute: int,
    events: Mapping[str, MatchEvent],
    stats: StatSource,
    significant: Mapping[str, bool] | None = None,
    outcomes: Callable[[str], list[OutcomeMention]] | None = None,
    allowed_evidence: Collection[str] | None = None,
    context_ids: Collection[str] = frozenset(),
    max_sentences: int = 3,
) -> Verdict:
    """Check a pivot card (or, with `significant`, a what-if comparison) against the data.

    `outcomes` is for comparisons: given a sentence, it returns each outcome the sentence
    names, so "more likely" style and significance words are checked against that outcome.
    `allowed_evidence`, when given, replaces the minute window: only those ids may be cited.
    `context_ids` are the ids of the match-context items the writer was shown (context.py).
    """
    issues: list[VerifierIssue] = []

    def issue(code: str, message: str, index: int | None = None) -> None:
        issues.append(VerifierIssue(code=code, message=message, sentence_index=index))

    lang = narrative.prefs.language
    up_words, down_words = lang_rules.up_words(lang), lang_rules.down_words(lang)
    if outcomes:
        up_words, down_words = up_words + lang_rules.likely_up(lang), down_words + lang_rules.likely_down(lang)
    max_words, max_headline = lang_rules.MAX_SENTENCE[lang], lang_rules.MAX_HEADLINE[lang]
    unit_name = "characters" if lang == "zh" else "words"

    # 1. Shape.
    if not 1 <= len(narrative.sentences) <= max_sentences:
        issue("sentence_count", f"Write 1 to {max_sentences} sentences, not {len(narrative.sentences)}.")
    if lang_rules.length(narrative.headline, lang) > max_headline:
        issue("too_long", f"The headline must be at most {max_headline} {unit_name}.")
    if re.search(r"\d", narrative.headline):
        issue("number_mismatch", "The headline must not contain digits.")
    banned = lang_rules.banned_terms(lang) + (JARGON if narrative.prefs.audience == "fan" else ())
    for term in _has_word(narrative.headline, banned):
        issue("banned_term", f"Remove '{term}' from the headline.")

    lo, hi = pivot_minute - EVIDENCE_BEFORE, pivot_minute + EVIDENCE_AFTER
    any_significant = bool(significant) and any(significant.values())

    for i, s in enumerate(narrative.sentences):
        words = lang_rules.length(s.text, lang)
        if words > max_words:
            issue("too_long", f"Sentence {i + 1} has {words} {unit_name}; keep it to {max_words}.", i)
        if not 1 <= len(s.evidence_ids) <= 4:
            issue("evidence_count", f"Sentence {i + 1} must cite 1 to 4 evidence ids.", i)

        # 2. Evidence.
        for eid in s.evidence_ids:
            event = events.get(eid)
            if event is None:
                issue("evidence_invalid", f"Evidence {eid} does not exist.", i)
            elif allowed_evidence is not None:
                if eid not in allowed_evidence:
                    issue("evidence_invalid", f"Evidence {eid} was not offered; cite one of "
                          f"{', '.join(sorted(allowed_evidence))}.", i)
            elif not lo <= event.minute <= hi:
                issue("evidence_invalid", f"Evidence {eid} is at minute {event.minute}, outside {lo}-{hi}.", i)

        # 3. Numbers: claims recompute, and the text carries no unclaimed numbers.
        for c in s.claims:
            actual, ref = _compute(stats, c.stat_ref), c.stat_ref
            if actual is None:
                issue("number_mismatch", f"{ref.metric} for {ref.team} in {ref.window[0]}-{ref.window[1]} "
                      "cannot be recomputed; drop the number.", i)
            elif abs(c.value - actual) > TOLERANCE[c.unit] + 1e-9:
                issue("number_mismatch",
                      f"{ref.metric} for {ref.team} in {ref.window[0]}-{ref.window[1]} is {actual:g}, not {c.value:g}.", i)
        for n in numbers_in(s.text, lang):
            if not any(_matches(n, c) for c in s.claims):
                issue("number_mismatch", f"The number {n} in sentence {i + 1} has no matching claim.", i)

        # 4. Direction words.
        up, down = _has_word(s.text, up_words), _has_word(s.text, down_words)
        deltas = _deltas(list(s.claims), stats) if up or down else []
        if (up or down) and not deltas and outcomes:
            for problem in _outcome_directions(s.text, outcomes(s.text), up_words, down_words):
                issue("direction_mismatch", problem, i)
        elif up or down:
            if not deltas:
                issue("direction_mismatch",
                      f"'{(up or down)[0]}' needs two claims on the same stat in different windows.", i)
            else:
                if up and not any(d > 0 for d in deltas):
                    issue("direction_mismatch", f"'{up[0]}' says it went up, but the numbers did not rise.", i)
                if down and not any(d < 0 for d in deltas):
                    issue("direction_mismatch", f"'{down[0]}' says it went down, but the numbers did not fall.", i)

        # 5. Significance wording, judged for every outcome the sentence names.
        for w in _has_word(s.text, lang_rules.significance_words(lang)):
            if not any_significant:
                issue("significance_unsupported", f"Do not say '{w}': the difference is not significant.", i)
            elif outcomes:
                named = outcomes(s.text)
                if not named:
                    issue("significance_unsupported", f"Say which result '{w}' is about.", i)
                for name in dict.fromkeys(m.outcome for m in named if not m.significant):
                    issue("significance_unsupported",
                          f"Do not say '{w}' about {name}: its intervals overlap, so that change is within noise.", i)

        # 6. Banned terms.
        for term in _has_word(s.text, banned):
            hint = " Fan versions use everyday words." if term in JARGON else ""
            issue("banned_term", f"Remove '{term}' from sentence {i + 1}.{hint}", i)

        # 7. Context.
        for cid in s.context_ids:
            if cid not in context_ids:
                issue("context_invalid", f"Context {cid} is not in the match context; cite only listed items.", i)

    return Verdict(passed=not issues, issues=issues)
