import pytest

from pivot_core.domain import ExplanationSentence, Narrative, ViewerPrefs
from pivot_worker.testing import claim
from pivot_worker.verifier import numbers_in, verify

PIVOT = 63


def card(*sentences, headline="Okafor's arrival flips the left flank"):
    return Narrative(prefs=ViewerPrefs(), headline=headline, sentences=list(sentences), source="llm")


def s(text, evidence=("m063-s01042",), claims=(), context_ids=()):
    return ExplanationSentence(text=text, evidence_ids=list(evidence), claims=list(claims), context_ids=list(context_ids))


def codes(verdict):
    return [i.code for i in verdict.issues]


def check(narrative, events, stats, **kw):
    return verify(narrative, pivot_minute=PIVOT, events=events, stats=stats, **kw)


GOOD = s("Okafor came on at 61' and final-third passes rose from 3 to 9 in the next five minutes.",
         claims=[claim("passes_final_third", "home", (56, 61), 3), claim("passes_final_third", "home", (61, 66), 9)])


def test_a_correct_card_passes(events, stats):
    verdict = check(card(GOOD), events, stats)
    assert verdict.passed, verdict.issues


# 1. Shape
def test_sentence_count(events, stats):
    assert codes(check(card(GOOD, GOOD, GOOD, GOOD), events, stats)) == ["sentence_count"]


def test_too_long_sentence_and_headline(events, stats):
    long = s(" ".join(["word"] * 31))
    assert codes(check(card(long, headline="one two three four five six seven eight nine"), events, stats)) == [
        "too_long", "too_long"]


def test_headline_digits(events, stats):
    assert codes(check(card(GOOD, headline="Rovers score 2 in 5 minutes"), events, stats)) == [
        "number_mismatch"]


# 2. Evidence
def test_unknown_evidence(events, stats):
    assert codes(check(card(s("Rovers pressed higher.", evidence=["m063-s99999"])), events, stats)) == [
        "evidence_invalid"]


def test_evidence_outside_window(events, stats):
    verdict = check(card(s("Rovers pressed higher.", evidence=["m063-s00100"])), events, stats)
    assert codes(verdict) == ["evidence_invalid"]
    assert "outside 55-68" in verdict.issues[0].message


# 3. Numbers
def test_wrong_claim_is_caught_with_the_real_value(events, stats):
    bad = s("Final-third passes reached 12.", claims=[claim("passes_final_third", "home", (61, 66), 12)])
    verdict = check(card(bad), events, stats)
    assert codes(verdict) == ["number_mismatch"]
    assert "is 9, not 12" in verdict.issues[0].message


def test_number_without_claim(events, stats):
    assert codes(check(card(s("Rovers had 72% possession after the switch.")), events, stats)) == ["number_mismatch"]


@pytest.mark.parametrize("written,ok", [("68%", True), ("68.4%", True), ("69%", False), ("74%", False)])
def test_rounded_numbers_match_their_claim(events, stats, written, ok):
    sent = s(f"Pass accuracy was {written} after the change.",
             claims=[claim("pass_accuracy_pct", "home", (61, 66), 68.4)])
    assert check(card(sent), events, stats).passed is ok


def test_percentage_tolerance(events, stats):
    near = s("Pass accuracy was 68.8%.", claims=[claim("pass_accuracy_pct", "home", (61, 66), 68.8)])
    far = s("Pass accuracy was 69.0%.", claims=[claim("pass_accuracy_pct", "home", (61, 66), 69.0)])
    assert check(card(near), events, stats).passed
    assert codes(check(card(far), events, stats)) == ["number_mismatch"]


def test_minutes_are_not_numbers():
    assert numbers_in("Okafor came on at 61' and again at 45+2', then 3 shots") == ["3"]


# 4. Direction
def test_direction_word_against_the_numbers(events, stats):
    bad = s("Pass accuracy rose from 74% to 68%.", claims=[
        claim("pass_accuracy_pct", "home", (56, 61), 74.2), claim("pass_accuracy_pct", "home", (61, 66), 68.4)])
    assert codes(check(card(bad), events, stats)) == ["direction_mismatch"]


def test_direction_word_needs_a_pair(events, stats):
    lone = s("Final-third passes rose to 9.", claims=[claim("passes_final_third", "home", (61, 66), 9)])
    assert codes(check(card(lone), events, stats)) == ["direction_mismatch"]


# 5. Significance
def test_significance_only_with_non_overlapping_intervals(events, stats):
    sent = s("Keeping Okafor on gives a significantly better chance of a draw.")
    assert codes(check(card(sent), events, stats)) == ["significance_unsupported"]
    assert codes(check(card(sent), events, stats, significant={"draw": False})) == ["significance_unsupported"]
    assert check(card(sent), events, stats, significant={"draw": True}).passed


# 6. Wording
def test_banned_terms(events, stats):
    sent = s("Harbour were definitely better and the odds shifted.")
    assert codes(check(card(sent), events, stats)) == ["banned_term", "banned_term"]


def test_banned_terms_match_whole_words_only(events, stats):
    assert check(card(s("The neverending pressure told.")), events, stats).passed


def test_likelihood_words_are_not_direction_words_on_pivot_cards(events, stats):
    text = s("After Okafor came on at 61', Harbour City looked more likely to score.")
    assert check(card(text), events, stats).passed
