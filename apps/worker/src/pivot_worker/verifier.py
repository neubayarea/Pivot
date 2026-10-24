"""Deterministic Verifier for explanations (D05, ADR-0005, architecture §6.3).

The Verifier never calls a model. It recomputes every claim through a `StatSource`
(B05's StatCalculator in production, a fake in tests) and checks six kinds of rule:

1. shape: sentence count, words per sentence, evidence count, headline length and numbers
2. evidence: every evidence id exists and falls from 8 minutes before the pivot to 5 after
3. numbers: every claim recomputes within tolerance in its stat's unit, and every number in the
   text is one of them, on a team and a stat the sentence is talking about
4. direction: rose/fell words match the sign of the change between two claimed windows
5. significance: "significant"-style words only when the what-if intervals do not overlap
6. wording: no banned terms, and no jargon in fan versions
7. context: every `context_ids` entry is a real item of the match context (D13)

Issue messages are written for the Explainer, which gets them back on a retry.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Iterable, Mapping
from functools import cache
from typing import Protocol

from pivot_core.domain import MatchEvent, Narrative, StatRef, Verdict, VerifierIssue
from pivot_core.domain.stats import STAT_UNITS, Claim

from . import languages as lang_rules
from .vocabulary import JARGON, STAT_TERMS

EVIDENCE_BEFORE, EVIDENCE_AFTER = 8, 5

# Allowed gap between a claimed value and the recomputed one, per unit.
TOLERANCE = {"count": 0.0, "pct": 0.5, "xg": 0.01, "index": 0.02, "m": 0.5, "km": 0.05, "ratio": 0.05}

# Numbers in running text, with their sign. Match minutes ("61'", "45+2'", "第61分钟") are not claims
# and are skipped. A digit right after a Chinese character still counts ("从3上升到9"), and a dash
# between two numbers ("3-1") is not a minus sign.
_NUMBER = re.compile(r"(?<![A-Za-z\d.])-?\d+(?:\.\d+)?")


class StatSource(Protocol):
    def compute(self, ref: StatRef) -> float: ...


def _compute(stats: StatSource, ref: StatRef) -> float | None:
    """Recompute a stat; None if the source has no data for it (or there is no StatCalculator yet).

    Any other error is a bug in the stat source and is raised, not reported as a wrong number.
    """
    try:
        return stats.compute(ref)
    except LookupError:                       # KeyError and IndexError included
        return None


def _plain(text: str, lang: str) -> str:
    return lang_rules.normalise(text, lang).replace("\u2212", "-")    # the typographic minus sign


def _numbers(plain: str, team_names: Iterable[str] = ()) -> list[tuple[int, str]]:
    """Numbers and where they start. Digits in team names ("FC 1899") and match minutes are not numbers."""
    for name in team_names:
        plain = plain.replace(name, " " * len(name))
    plain = lang_rules.MINUTES.sub(lambda m: " " * len(m.group()), plain)
    return [(m.start(), m.group()) for m in _NUMBER.finditer(plain)]


def numbers_in(text: str, lang: str = "en", team_names: Iterable[str] = ()) -> list[str]:
    return [n for _, n in _numbers(_plain(text, lang), team_names)]


def _pattern(phrase: str) -> str:
    if lang_rules.has_cjk(phrase):            # no word boundaries in Chinese
        return re.escape(phrase)
    return rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])"


def _mentions(text: str, phrases: Mapping[str, frozenset[str]]) -> list[tuple[int, frozenset[str]]]:
    """Where each phrase occurs, longest first, so "final-third passes" is not also read as "passes"."""
    taken = [False] * len(text)
    found = []
    for phrase in sorted(phrases, key=len, reverse=True):
        for m in re.finditer(_pattern(phrase), text):
            if not any(taken[m.start():m.end()]):
                taken[m.start():m.end()] = [True] * (m.end() - m.start())
                found.append((m.start(), phrases[phrase]))
    return found


@cache
def _stat_names(lang: str) -> dict[str, frozenset[str]]:
    """Lower-cased stat names a sentence may use, each with every stat it could mean.

    A name counts for every stat whose name contains it, so "passes" may be any kind of pass.
    """
    names: dict[str, set[str]] = {}
    for metric, term in STAT_TERMS.items():
        for label in (term.label, term.fan_label, lang_rules.LABELS.get(lang, {}).get(metric, "")):
            for part in re.split(r"[()]", label.lower()):                 # "expected goals (xG)"
                part = re.sub(r"^(el|la|los|las) ", "", part.strip())     # "la amenaza creada"
                if part:
                    names.setdefault(part, set()).add(metric)
    return {name: frozenset(m for other, ms in names.items() if re.search(_pattern(name), other) for m in ms)
            for name in names}


def _matches(number: str, claim: Claim, actual: float | None) -> bool:
    """True if a number as written could be the claim's recomputed value (allowing for rounding).

    It is compared with the real value, not the claimed one, so the claim tolerance and the
    rounding slack are not added together. Without a real value (the claim is already reported
    as wrong) it is compared with the claim.
    """
    decimals = len(number.split(".")[1]) if "." in number else 0
    slack = max(TOLERANCE[STAT_UNITS[claim.stat_ref.metric]], 0.5 * 10**-decimals)
    return abs(float(number) - (claim.value if actual is None else actual)) <= slack + 1e-9


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
    outcome_deltas: Callable[[str], list[float]] | None = None,
    context_ids: Collection[str] = frozenset(),
    team_names: Mapping[str, str] | None = None,
    max_sentences: int = 3,
) -> Verdict:
    """Check a pivot card (or, with `significant`, a what-if comparison) against the data.

    `outcome_deltas` is for comparisons: given a sentence, it returns the change in each
    outcome the sentence mentions, so "more likely" style words can be checked without claims.
    `context_ids` are the ids of the match-context items the writer was shown (context.py).
    `team_names` ("home"/"away" to display names) let the number check see which team a number is about.
    """
    issues: list[VerifierIssue] = []

    def issue(code: str, message: str, index: int | None = None) -> None:
        issues.append(VerifierIssue(code=code, message=message, sentence_index=index))

    lang = narrative.prefs.language
    up_words, down_words = lang_rules.up_words(lang), lang_rules.down_words(lang)
    max_words, max_headline = lang_rules.MAX_SENTENCE[lang], lang_rules.MAX_HEADLINE[lang]
    unit_name = "characters" if lang == "zh" else "words"
    names = dict(team_names or {})
    team_phrases = {name: frozenset([side]) for side, name in names.items()}

    # 1. Shape.
    if not 1 <= len(narrative.sentences) <= max_sentences:
        issue("sentence_count", f"Write 1 to {max_sentences} sentences, not {len(narrative.sentences)}.")
    if lang_rules.length(narrative.headline, lang) > max_headline:
        issue("too_long", f"The headline must be at most {max_headline} {unit_name}.")
    if re.search(r"\d", narrative.headline):
        issue("number_mismatch", "The headline must not contain digits.")
    if spelled := lang_rules.number_words(narrative.headline, lang):
        issue("number_mismatch", f"The headline must not contain numbers, even as words: remove '{spelled[0]}'.")
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

        # 3. Numbers: claims recompute in their stat's unit, and the text carries no unclaimed numbers.
        actuals = [_compute(stats, c.stat_ref) for c in s.claims]
        for k, (c, actual) in enumerate(zip(s.claims, actuals)):
            ref, unit = c.stat_ref, STAT_UNITS[c.stat_ref.metric]
            where = f"{ref.metric} for {ref.team} in {ref.window[0]}-{ref.window[1]}"
            if c.unit != unit:
                issue("number_mismatch", f"{where} is measured in {unit}, not {c.unit}.", i)
            if actual is None:
                issue("number_mismatch", f"{where} cannot be recomputed; drop the number.", i)
            elif abs(c.value - actual) > TOLERANCE[unit] + 1e-9:
                issue("number_mismatch", f"{where} is {actual:g}, not {c.value:g}.", i)
                actuals[k] = None             # reported once: its number in the text is checked against the claim
        # A number belongs to a team named before it and to a stat the sentence names, when it names any.
        plain = _plain(s.text, lang)
        teams = _mentions(plain, team_phrases)
        named_stats = {m for _, ms in _mentions(plain.lower(), _stat_names(lang)) for m in ms}
        for at, n in _numbers(plain, names.values()):
            before = {side for start, sides in teams if start < at for side in sides}
            same = [c for c, actual in zip(s.claims, actuals) if _matches(n, c, actual)]
            fits = [c for c in same if (not before or c.stat_ref.team in before)
                    and (not named_stats or c.stat_ref.metric in named_stats)]
            if not same:
                issue("number_mismatch", f"The number {n} in sentence {i + 1} has no matching claim.", i)
            elif not fits:
                said = ([f"about {' or '.join(names[side] for side in sorted(before))}"] if before else []) + \
                    ([f"on {' or '.join(sorted(named_stats))}"] if named_stats else [])
                claimed = ", ".join(f"{c.stat_ref.metric} for {names.get(c.stat_ref.team, c.stat_ref.team)}"
                                    for c in same)
                issue("number_mismatch", f"The number {n} in sentence {i + 1} only matches {claimed}, but the "
                      f"sentence has it {' and '.join(said)}; cite the claim for what the sentence says.", i)

        # 4. Direction words.
        up, down = _has_word(s.text, up_words), _has_word(s.text, down_words)
        if up or down:
            deltas = _deltas(list(s.claims), stats) or (outcome_deltas(s.text) if outcome_deltas else [])
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
