"""Deterministic Verifier for explanations (D05, ADR-0005, architecture §6.3).

The Verifier never calls a model. It recomputes every claim through a `StatSource`
(B05's StatCalculator in production, a fake in tests) and checks six kinds of rule:

1. shape: sentence count, words per sentence, evidence count, headline length and digits
2. evidence: every evidence id exists and falls from 8 minutes before the pivot to 5 after
3. numbers: every claim recomputes within tolerance, and every number in the text has a claim
4. direction: rose/fell words match the sign of the change between two claimed windows, "from A to B"
   follows the order of the windows, and doubled/halved-style words match the ratio
5. significance: "significant"-style words only when the what-if intervals do not overlap
6. wording: no banned terms, and no jargon in fan versions
7. context: every `context_ids` entry is a real item of the match context (D13)

Issue messages are written for the Explainer, which gets them back on a retry.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Mapping
from typing import Protocol

from pivot_core.domain import MatchEvent, Narrative, StatRef, Verdict, VerifierIssue
from pivot_core.domain.stats import Claim

from . import languages as lang_rules
from .vocabulary import JARGON

EVIDENCE_BEFORE, EVIDENCE_AFTER = 8, 5

# Allowed gap between a claimed value and the recomputed one, per unit.
TOLERANCE = {"count": 0.0, "pct": 0.5, "xg": 0.01, "index": 0.02, "m": 0.5, "km": 0.05, "ratio": 0.05}

# Numbers in running text. Match minutes ("61'", "45+2'", "第61分钟") and lengths of time ("five
# minutes") are not claims and are skipped. A digit right after a Chinese character still counts
# ("从3上升到9"), and numbers written as words count too ("从三上升到十二", "de tres a doce").
_NUMBER = re.compile(r"(?<![A-Za-z\d.])\d+(?:\.\d+)?")


class StatSource(Protocol):
    def compute(self, ref: StatRef) -> float: ...


def _compute(stats: StatSource, ref: StatRef) -> float | None:
    """Recompute a stat; None if the source cannot (missing data, or no StatCalculator yet)."""
    try:
        return stats.compute(ref)
    except Exception:
        return None


# How far the real ratio may be from a magnitude word: "doubled" accepts 1.5x to 2.5x, "tripled"
# 2.5x to 3.5x, "halved" 0.375x to 0.625x.
def _magnitude_fits(factor: float, before: float, after: float) -> bool:
    return before != 0 and abs(after / before - factor) <= 0.25 * min(factor, 2.0)


def _plain(text: str, lang: str) -> str:
    """The text with digits for every number that is a claim, and nothing else numeric."""
    text = lang_rules.mask_minutes(lang_rules.normalise(text, lang))
    for w in _has_word(text, tuple(lang_rules.magnitude_words(lang))):   # "翻了两番" is not the number 2
        text = re.sub(re.escape(w), " ", text, flags=re.IGNORECASE)
    return lang_rules.DURATION.sub(" ", lang_rules.spell_out(text, lang))


def numbers_in(text: str, lang: str = "en") -> list[str]:
    return _NUMBER.findall(_plain(text, lang))


def _matches(number: str, claim: Claim) -> bool:
    """True if a number as written could be the claim's value (allowing for rounding)."""
    decimals = len(number.split(".")[1]) if "." in number else 0
    slack = max(TOLERANCE[claim.unit], 0.5 * 10**-decimals)
    return abs(float(number) - claim.value) <= slack + 1e-9


def _has_word(text: str, words: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    found = []
    for w in words:
        if lang_rules.has_cjk(w):                 # no word boundaries in Chinese
            if w in text:
                found.append(w)
            continue
        pattern = re.escape(w.lower()) if not w[0].isalnum() or not w[-1].isalnum() else rf"\b{re.escape(w.lower())}\b"
        if re.search(pattern, lowered):
            found.append(w)
    return found


def _key(c: Claim) -> tuple:
    return c.stat_ref.metric, c.stat_ref.team, c.stat_ref.player_id


def _pairs(claims: list[Claim], stats: StatSource) -> list[tuple[float, float]]:
    """Recomputed (earlier, later) values of claims on the same stat in two different windows."""
    by_stat: dict[tuple, list[Claim]] = {}
    for c in claims:
        by_stat.setdefault(_key(c), []).append(c)
    pairs = []
    for group in by_stat.values():
        group = sorted(group, key=lambda c: c.stat_ref.window)
        for a, b in zip(group, group[1:]):
            va, vb = _compute(stats, a.stat_ref), _compute(stats, b.stat_ref)
            if a.stat_ref.window != b.stat_ref.window and va is not None and vb is not None:
                pairs.append((va, vb))
    return pairs


def _backwards(text: str, lang: str, claims: list[Claim]) -> list[tuple[str, str]]:
    """"from A to B" phrases where A is the later window's value and B the earlier one's."""
    wrong = []
    for a, b in lang_rules.FROM_TO[lang].findall(_plain(text, lang)):
        orders = {ca.stat_ref.window < cb.stat_ref.window
                  for ca in claims if _matches(a, ca) for cb in claims
                  if _matches(b, cb) and _key(ca) == _key(cb) and ca.stat_ref.window != cb.stat_ref.window}
        if orders == {False}:
            wrong.append((a, b))
    return wrong


def verify(
    narrative: Narrative,
    *,
    pivot_minute: int,
    events: Mapping[str, MatchEvent],
    stats: StatSource,
    significant: Mapping[str, bool] | None = None,
    outcome_deltas: Callable[[str], list[float]] | None = None,
    context_ids: Collection[str] = frozenset(),
    max_sentences: int = 3,
) -> Verdict:
    """Check a pivot card (or, with `significant`, a what-if comparison) against the data.

    `outcome_deltas` is for comparisons: given a sentence, it returns the change in each
    outcome the sentence mentions, so "more likely" style words can be checked without claims.
    `context_ids` are the ids of the match-context items the writer was shown (context.py).
    """
    issues: list[VerifierIssue] = []

    def issue(code: str, message: str, index: int | None = None) -> None:
        issues.append(VerifierIssue(code=code, message=message, sentence_index=index))

    lang = narrative.prefs.language
    up_words, down_words = lang_rules.up_words(lang), lang_rules.down_words(lang)
    magnitude_words = lang_rules.magnitude_words(lang)
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
    allow_significance = bool(significant) and any(significant.values())

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

        # 4. Direction words, the order of "from A to B", and magnitude words.
        pairs = _pairs(list(s.claims), stats)
        for a, b in _backwards(s.text, lang, list(s.claims)):
            issue("direction_mismatch", f"'{a} to {b}' is backwards: {b} is the earlier value and {a} the later one.", i)
        for w, factor in magnitude_words.items():
            if not _has_word(s.text, (w,)) or not pairs:
                continue
            if not any(_magnitude_fits(factor, va, vb) for va, vb in pairs):
                ratios = ", ".join(f"{vb / va:.2g}x" if va else "from zero" for va, vb in pairs)
                issue("number_mismatch", f"'{w}' means about {factor:g}x, but the change was {ratios}.", i)
        up, down = _has_word(s.text, up_words), _has_word(s.text, down_words)
        if up or down:
            deltas = [vb - va for va, vb in pairs] or (outcome_deltas(s.text) if outcome_deltas else [])
            if not deltas:
                issue("direction_mismatch",
                      f"'{(up or down)[0]}' needs two claims on the same stat in different windows"
                      f"{' or a named outcome' if outcome_deltas else ''}.", i)
            else:
                if up and not any(d > 0 for d in deltas):
                    issue("direction_mismatch", f"'{up[0]}' says it went up, but the numbers did not rise.", i)
                if down and not any(d < 0 for d in deltas):
                    issue("direction_mismatch", f"'{down[0]}' says it went down, but the numbers did not fall.", i)

        # 5. Significance wording.
        if not allow_significance:
            for w in _has_word(s.text, lang_rules.significance_words(lang)):
                issue("significance_unsupported", f"Do not say '{w}': the difference is not significant.", i)

        # 6. Banned terms.
        for term in _has_word(s.text, banned):
            hint = " Fan versions use everyday words." if term in JARGON else ""
            issue("banned_term", f"Remove '{term}' from sentence {i + 1}.{hint}", i)

        # 7. Context.
        for cid in s.context_ids:
            if cid not in context_ids:
                issue("context_invalid", f"Context {cid} is not in the match context; cite only listed items.", i)

    return Verdict(passed=not issues, issues=issues)
