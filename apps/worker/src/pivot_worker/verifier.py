"""Deterministic Verifier for explanations (D05, ADR-0005, architecture §6.3).

The Verifier never calls a model. It recomputes every claim through a `StatSource`
(B05's StatCalculator in production, a fake in tests) and checks six kinds of rule:

1. shape: sentence count, words per sentence, evidence count, headline length and numbers
2. evidence: every evidence id exists and falls from 8 minutes before the pivot to 5 after
   (comparisons instead cite only the ids they were offered; with no event in that window, a
   template sentence without numbers cites `NO_EVIDENCE`)
3. numbers: every claim recomputes within tolerance in its stat's unit, and every number in the
   text is one of them, on a team and a stat the sentence is talking about ("ten men" is checked
   against the red cards instead)
4. direction: rose/fell words match the sign of the change between two claimed windows, "from A to B"
   follows the order of the windows, and doubled/halved and "three times as many" style words match the ratio; in
   comparisons, "more likely" style words match the outcome they describe
5. significance: "significant"-style words only about outcomes whose what-if intervals do not overlap
6. wording: no banned terms; fan versions use no jargon and at most one number per sentence
7. context: every cited item was shown to the writer and is about someone in the sentence, and
   any off-pitch story ("former club", "feud") cites one (D13)
8. score: in pivot cards, words about the score ("equaliser", "extend the lead", "trailing") fit the
   real score before and after the goal they describe, or around the pivot (Dx8)

Issue messages are written for the Explainer, which gets them back on a retry.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from functools import cache
from typing import NamedTuple, Protocol

from pivot_core.domain import MatchEvent, Narrative, StatRef, Verdict, VerifierIssue
from pivot_core.domain.stats import STAT_UNITS, Claim

from . import languages as lang_rules
from .context import ContextItem, involved_in, mentions
from .matchstate import men_at, score_line
from .scenarios import is_goal
from .vocabulary import STAT_TERMS

EVIDENCE_BEFORE, EVIDENCE_AFTER = 8, 5
# What a template sentence cites when no event falls in the evidence window: it is accepted only
# then, only from the template, and only for a sentence with no numbers, claims or context.
NO_EVIDENCE = "none"

# Allowed gap between a claimed value and the recomputed one, per unit.
TOLERANCE = {"count": 0.0, "pct": 0.5, "xg": 0.01, "index": 0.02, "m": 0.5, "km": 0.05, "ratio": 0.05}

# Numbers in running text, with their sign. Match minutes ("61'", "45+2'", "第61分钟") and lengths of
# time ("five minutes") are not claims and are skipped. A digit right after a Chinese character still
# counts ("从3上升到9"), numbers written as words count too ("从三上升到十二", "de tres a doce"), and a
# dash between two numbers ("3-1") is not a minus sign.
_NUMBER = re.compile(r"(?<![A-Za-z\d.])-?\d+(?:\.\d+)?")


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
    """Recompute a stat; None if the source has no data for it (or there is no StatCalculator yet).

    Any other error is a bug in the stat source and is raised, not reported as a wrong number.
    """
    try:
        return stats.compute(ref)
    except LookupError:                       # KeyError and IndexError included
        return None


# How far the real ratio may be from a magnitude word: "doubled" accepts 1.5x to 2.5x, "tripled"
# 2.5x to 3.5x, "halved" 0.375x to 0.625x.
def _magnitude_fits(factor: float, before: float, after: float) -> bool:
    return before != 0 and abs(after / before - factor) <= 0.25 * min(factor, 2.0)


def _plain(text: str, lang: str) -> str:
    """The text with digits for every number that is a claim, and nothing else numeric."""
    return lang_rules.mask_multiples(lang_rules.DURATION.sub(" ", _spelled(text, lang)), lang)


def _spelled(text: str, lang: str) -> str:
    """`_plain` before lengths of time and multiples are taken out."""
    text = lang_rules.normalise(text, lang)
    text = text.replace("\u2212", "-").replace("\u2013", "-")       # typographic minus signs ("−0.32", "–0.32")
    text = lang_rules.mask_minutes(text)
    for w in _has_word(text, tuple(lang_rules.magnitude_words(lang))):   # "翻了两番" is not the number 2
        text = re.sub(re.escape(w), " ", text, flags=re.IGNORECASE)
    return lang_rules.spell_out(text, lang)


def _numbers(plain: str, team_names: Iterable[str] = ()) -> list[tuple[int, str]]:
    """Numbers in `_plain` text and where they start. Digits in team names ("FC 1899") are not numbers."""
    for name in team_names:
        plain = plain.replace(name, " " * len(name))
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


def _word_pattern(w: str) -> str:
    if lang_rules.has_cjk(w) or not w[0].isalnum() or not w[-1].isalnum():   # no word boundaries in Chinese
        return re.escape(w.lower())
    return rf"\b{re.escape(w.lower())}\b"


def _spans(text: str, words: tuple[str, ...]) -> list[tuple[int, int, str]]:
    lowered = text.lower()
    return sorted((m.start(), m.end(), w) for w in words for m in re.finditer(_word_pattern(w), lowered))


def _has_word(text: str, words: tuple[str, ...]) -> list[str]:
    found = {w for *_, w in _spans(text, words)}
    return [w for w in words if w in found]


def _direction_words(text: str, lang: str, words: tuple[str, ...]) -> list[str]:
    """Direction words in `text`, except those about players on the pitch ("dropped to ten men", "降至10人")."""
    spelled = lang_rules.spell_out(lang_rules.normalise(text, lang), lang)
    counts = lang_rules.player_counts(spelled, lang)
    found = {w for _, end, w in _spans(spelled, words)
             if not any(at >= end and len(spelled[end:at]) <= 12 and not re.search(r"\d", spelled[end:at])
                        for at in counts)}
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
                  for ca in claims if _matches(a, ca, None) for cb in claims
                  if _matches(b, cb, None) and _key(ca) == _key(cb) and ca.stat_ref.window != cb.stat_ref.window}
        if orders == {False}:
            wrong.append((a, b))
    return wrong


class Goal(NamedTuple):
    event: MatchEvent
    before: dict[str, int]
    after: dict[str, int]
    trailed: bool                             # the scorer's side had been behind earlier in the match


def _goals(events: Mapping[str, MatchEvent]) -> list[Goal]:
    """Every goal with the score just before and just after it."""
    score, behind, goals = {"home": 0, "away": 0}, {"home": False, "away": False}, []
    for e in sorted((e for e in events.values() if is_goal(e)), key=lambda e: (e.t, e.seq)):
        after = {**score, e.team: score[e.team] + 1}
        goals.append(Goal(e, score, after, behind[e.team]))
        score = after
        for side, other in (("home", "away"), ("away", "home")):
            behind[side] |= score[side] < score[other]
    return goals


def _lead(score: Mapping[str, int], side: str) -> int:
    return score[side] - score["away" if side == "home" else "home"]


# What each goal word says about the score before (b) and after (a) the goal, from the scorer's side.
GOAL_WORDS = {
    "equaliser": lambda g, b, a: a == 0,
    "take_lead": lambda g, b, a: b == 0 and a > 0,
    "extend_lead": lambda g, b, a: b > 0 and a > b,
    "comeback": lambda g, b, a: a >= 0 and g.trailed,
}


def _score_words(text: str, lang: str) -> list[tuple[int, str, str]]:
    """(position, kind, word) of each score word, longest first so "chasing an equaliser" is not an equaliser."""
    lowered, taken, found = text.lower(), [False] * len(text), []
    words = sorted(((w, kind) for kind, ws in lang_rules.score_words(lang).items() for w in ws),
                   key=lambda wk: len(wk[0]), reverse=True)
    for w, kind in words:
        for m in re.finditer(_word_pattern(w), lowered):
            if not any(taken[m.start():m.end()]):
                taken[m.start():m.end()] = [True] * (m.end() - m.start())
                found.append((m.start(), kind, w))
    return sorted(found)


def _score_problems(text: str, lang: str, goals: list[Goal], cited: Collection[str], window: tuple[int, int],
                    names: Mapping[str, str]) -> list[str]:
    """Score words in `text` that do not fit the real score.

    A goal word is about the goals the text cites, or else any goal in the window, preferring the
    side named nearest before it; a state word ("trailing") is about the side named nearest it at
    any point in the window.
    """
    lo, hi = window
    lowered = text.lower()
    sides = sorted((m.start(), side) for side, name in names.items()
                   for m in re.finditer(re.escape(name.lower()), lowered))
    in_window = [g for g in goals if lo <= g.event.minute <= hi]
    problems = []
    for at, kind, word in _score_words(text, lang):
        side = next((s for start, s in reversed(sides) if start < at), None) or \
            next((s for start, s in sides if start > at), None)
        if kind in GOAL_WORDS:
            pool = [g for g in goals if g.event.event_id in cited] or in_window
            pool = [g for g in pool if g.event.team == side] or pool
            if any(GOAL_WORDS[kind](g, _lead(g.before, g.event.team), _lead(g.after, g.event.team)) for g in pool):
                continue
            if not pool:
                problems.append(f"'{word}' describes a goal, but there is no goal from {lo + 1}' to {hi + 1}'.")
                continue
            facts = "; ".join(f"the {g.event.clock_label} goal by {names[g.event.team]} made it "
                              f"{score_line(g.after, names)} (it was {score_line(g.before, names)})" for g in pool[:2])
            problems.append(f"'{word}' does not fit the score: {facts}.")
        else:
            start = max([g for g in goals if g.event.minute < lo], key=lambda g: g.event.t, default=None)
            scores = [start.after if start else {"home": 0, "away": 0}] + [g.after for g in in_window]
            who = [side] if side else ["home", "away"]
            sign = -1 if kind == "trailing" else 1
            if any(sign * _lead(sc, s) > 0 for sc in scores for s in who):
                continue
            team = names[side] if side else "neither side"
            state = "behind" if kind == "trailing" else "ahead"
            seq = ", then ".join(dict.fromkeys(score_line(sc, names) for sc in scores))
            problems.append(f"'{word}' does not fit the score: {team} was not {state} from {lo + 1}' to {hi + 1}' "
                            f"({seq}).")
    return problems


def verify(
    narrative: Narrative,
    *,
    pivot_minute: int,
    events: Mapping[str, MatchEvent],
    stats: StatSource,
    significant: Mapping[str, bool] | None = None,
    outcomes: Callable[[str], list[OutcomeMention]] | None = None,
    allowed_evidence: Collection[str] | None = None,
    context: Sequence[ContextItem] = (),
    team_names: Mapping[str, str] | None = None,
    max_sentences: int = 3,
) -> Verdict:
    """Check a pivot card (or, with `significant`, a what-if comparison) against the data.

    `outcomes` is for comparisons: given a sentence, it returns each outcome the sentence
    names, so "more likely" style and significance words are checked against that outcome.
    `allowed_evidence`, when given, replaces the minute window: only those ids may be cited.
    `context` is the match-context items the writer was shown (`explainer.shown_context`).
    `team_names` ("home"/"away" to display names) let the number check see which team a number is about.
    """
    issues: list[VerifierIssue] = []

    def issue(code: str, message: str, index: int | None = None) -> None:
        issues.append(VerifierIssue(code=code, message=message, sentence_index=index))

    lang = narrative.prefs.language
    up_words, down_words = lang_rules.up_words(lang), lang_rules.down_words(lang)
    magnitude_words = lang_rules.magnitude_words(lang)
    if outcomes:
        up_words, down_words = up_words + lang_rules.likely_up(lang), down_words + lang_rules.likely_down(lang)
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
    fan = narrative.prefs.audience == "fan"
    jargon = lang_rules.jargon(lang) if fan else ()
    banned = lang_rules.banned_terms(lang) + jargon
    for term in _has_word(narrative.headline, banned):
        issue("banned_term", f"Remove '{term}' from the headline.")
    shown = {item.context_id: item for item in context}
    off_pitch = lang_rules.off_pitch_words(lang)

    def off_pitch_story(text: str) -> list[str]:
        return _has_word(text, off_pitch) or lang_rules.off_pitch_names(text)

    if (story := off_pitch_story(narrative.headline)) and not any(s.context_ids for s in narrative.sentences):
        issue("context_invalid", f"The headline tells an off-pitch story ('{story[0]}'); cite its context item "
              "in a sentence, or drop it.")

    lo, hi = pivot_minute - EVIDENCE_BEFORE, pivot_minute + EVIDENCE_AFTER
    # 8. Score words, in pivot cards only: comparisons talk about results ("a draw"), not the live score.
    score_check = outcomes is None and significant is None
    if score_check:
        goals, sides = _goals(events), names or {"home": "home", "away": "away"}
        all_cited = {e for s in narrative.sentences for e in s.evidence_ids}
        for problem in _score_problems(narrative.headline, lang, goals, all_cited, (lo, hi), sides):
            issue("number_mismatch", f"Headline: {problem}")
    any_significant = bool(significant) and any(significant.values())
    nothing_to_cite = not any(lo <= e.minute <= hi for e in events.values()) if allowed_evidence is None else False

    for i, s in enumerate(narrative.sentences):
        words = lang_rules.length(s.text, lang)
        if words > max_words:
            issue("too_long", f"Sentence {i + 1} has {words} {unit_name}; keep it to {max_words}.", i)
        if not 1 <= len(s.evidence_ids) <= 4:
            issue("evidence_count", f"Sentence {i + 1} must cite 1 to 4 evidence ids.", i)

        # 2. Evidence.
        for eid in s.evidence_ids:
            event = events.get(eid)
            if eid == NO_EVIDENCE and event is None and s.evidence_ids == [NO_EVIDENCE] and nothing_to_cite \
                    and narrative.source == "template" and not s.claims and not s.context_ids \
                    and not numbers_in(s.text, lang, names.values()) and not lang_rules.number_words(s.text, lang):
                continue
            if event is None:
                issue("evidence_invalid", f"Evidence {eid} does not exist.", i)
            elif allowed_evidence is not None:
                if eid not in allowed_evidence:
                    issue("evidence_invalid", f"Evidence {eid} was not offered; cite one of "
                          f"{', '.join(sorted(allowed_evidence))}.", i)
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
        numbers = _numbers(plain, names.values())
        # "Ten men" is not a stat: it must be the players either side had at an event the sentence cites.
        counts = lang_rules.player_counts(plain, lang)
        on_pitch = {n for e in s.evidence_ids if e in events for n in men_at(events.values(), events[e].t).values()}
        for at, n in numbers:
            if at in counts:
                if counts[at] not in on_pitch:
                    had = " or ".join(map(str, sorted(on_pitch))) or "11"
                    issue("number_mismatch", f"Sentence {i + 1} says {n} players, but at the events it cites the "
                          f"teams had {had} on the pitch.", i)
                continue
            before = {side for start, sides in teams if start < at for side in sides}
            same = [c for c, actual in zip(s.claims, actuals) if _matches(n, c, actual)]
            fits = [c for c in same if (not before or c.stat_ref.team in before)
                    and (not named_stats or c.stat_ref.metric in named_stats)]
            if not same:
                issue("number_mismatch", f"The number {n} in sentence {i + 1} has no matching claim; "
                      "copy one from the stat sheet or drop the number.", i)
            elif not fits:
                said = ([f"about {' or '.join(names[side] for side in sorted(before))}"] if before else []) + \
                    ([f"on {' or '.join(sorted(named_stats))}"] if named_stats else [])
                claimed = ", ".join(f"{c.stat_ref.metric} for {names.get(c.stat_ref.team, c.stat_ref.team)}"
                                    for c in same)
                issue("number_mismatch", f"The number {n} in sentence {i + 1} only matches {claimed}, but the "
                      f"sentence has it {' and '.join(said)}; cite the claim for what the sentence says.", i)
        if fan and len(numbers) > 1:
            issue("number_mismatch", f"Sentence {i + 1} has {len(numbers)} numbers; fan versions use at most one "
                  "number per sentence (keep both claims, write only the newer value).", i)

        # 4. Direction words, the order of "from A to B", and magnitude words.
        pairs = _pairs(list(s.claims), stats)
        for a, b in _backwards(s.text, lang, list(s.claims)):
            issue("direction_mismatch", f"'{a} to {b}' is backwards: {b} is the earlier value and {a} the later one.", i)
        magnitudes = [(w, f) for w, f in magnitude_words.items() if _has_word(s.text, (w,))]
        multiples = lang_rules.multiples(_spelled(s.text, lang), lang)
        if multiples and not pairs:
            issue("number_mismatch", f"'{multiples[0][0].strip()}' needs two claims on the same stat in different "
                  "windows.", i)
        for w, factor in magnitudes + multiples:
            if not pairs:
                continue
            if not any(_magnitude_fits(factor, va, vb) for va, vb in pairs):
                ratios = ", ".join(f"{vb / va:.2g}x" if va else "from zero" for va, vb in pairs)
                issue("number_mismatch", f"'{w}' means about {factor:g}x, but the change was {ratios}.", i)
        up, down = _direction_words(s.text, lang, up_words), _direction_words(s.text, lang, down_words)
        deltas = [vb - va for va, vb in pairs] if up or down else []
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
            hint = " Fan versions use everyday words." if term in jargon else ""
            issue("banned_term", f"Remove '{term}' from sentence {i + 1}.{hint}", i)

        # 7. Context: only listed items, about someone in this sentence; off-pitch stories need one.
        people = set().union(*(involved_in(events[e]) for e in s.evidence_ids if e in events))
        for cid in s.context_ids:
            item = shown.get(cid)
            if item is None:
                issue("context_invalid", f"Context {cid} is not in the match context; cite only listed items.", i)
            elif not mentions(item, s.text, people):
                who = " and ".join(item.subject_names or item.subject_ids)
                issue("context_invalid", f"Context {cid} is about {who}, who is neither named in sentence {i + 1} "
                      "nor in its evidence.", i)
        if not s.context_ids and (story := off_pitch_story(s.text)):
            issue("context_invalid", f"'{story[0]}' tells an off-pitch story; cite the match-context item it "
                  "comes from, or drop it.", i)

        # 8. Score words.
        if score_check:
            for problem in _score_problems(s.text, lang, goals, s.evidence_ids, (lo, hi), sides):
                issue("number_mismatch", f"Sentence {i + 1}: {problem}", i)

    return Verdict(passed=not issues, issues=issues)
