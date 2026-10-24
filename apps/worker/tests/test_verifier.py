import pytest

from pivot_core.domain import ExplanationSentence, Narrative, StatRef, ViewerPrefs
from pivot_core.domain.stats import Claim
from pivot_worker.testing import FakeStats, claim
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
    assert codes(check(card(long, headline=" ".join(["word"] * 9)), events, stats)) == [
        "too_long", "too_long"]


def test_headline_digits(events, stats):
    assert codes(check(card(GOOD, headline="Rovers score 2 in 5 minutes"), events, stats)) == [
        "number_mismatch"]


@pytest.mark.parametrize("headline,ok", [
    ("Two goals in three minutes", False),
    ("Rovers' twenty-minute storm", False),
    ("No one stops Rovers now", True),            # "one" doubles as a pronoun, so it is allowed
    ("Okafor's arrival flips the left flank", True),
])
def test_headline_numbers_written_as_words(events, stats, headline, ok):
    assert codes(check(card(GOOD, headline=headline), events, stats)) == ([] if ok else ["number_mismatch"])


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


# Gaps found in the #76 review (Dx1). Each test failed before the fix.
NAMES = {"home": "Rovers", "away": "Harbour"}


def test_a_number_must_come_from_a_claim_on_the_team_it_is_written_about(events):
    away_only = FakeStats({("shots", "away", (61, 66)): 3})
    claims = [claim("shots", "away", (61, 66), 3)]
    wrong = check(card(s("Rovers had 3 shots after the change.", claims=claims)), events, away_only, team_names=NAMES)
    assert codes(wrong) == ["number_mismatch"]
    assert "Rovers" in wrong.issues[0].message
    assert check(card(s("Harbour had 3 shots after the change.", claims=claims)), events, away_only,
                 team_names=NAMES).passed


def test_a_number_must_come_from_a_claim_on_a_stat_the_sentence_names(events, stats):
    passes = [claim("passes_final_third", "home", (56, 61), 3)]
    assert codes(check(card(s("Rovers had 3 shots before the change.", claims=passes)), events, stats,
                       team_names=NAMES)) == ["number_mismatch"]
    assert check(card(s("Rovers had 3 final-third passes before the change.", claims=passes)), events, stats,
                 team_names=NAMES).passed


def test_team_and_stat_checks_allow_natural_wording(events, stats):
    pair = [claim("passes_final_third", "home", (56, 61), 3), claim("passes_final_third", "home", (61, 66), 9)]
    fan = s("Their passes into the attacking third rose from 3 to 9, and Harbour were hanging on.", claims=pair)
    pinned = s("Rovers pinned Harbour back as their final-third passes rose from 3 to 9.", claims=pair)
    for sentence in (fan, pinned):
        verdict = check(card(sentence), events, stats, team_names=NAMES)
        assert verdict.passed, verdict.issues


def test_negative_numbers_keep_their_sign(events):
    momentum = FakeStats({("momentum_avg", "home", (61, 66)): -0.32})
    claims = [claim("momentum_avg", "home", (61, 66), -0.32)]
    assert check(card(s("Rovers' momentum was -0.32 after the change.", claims=claims)), events, momentum).passed
    assert check(card(s("Rovers' momentum was −0.32 after the change.", claims=claims)), events, momentum).passed
    assert codes(check(card(s("Rovers' momentum was 0.32 after the change.", claims=claims)), events,
                       momentum)) == ["number_mismatch"]
    assert numbers_in("momentum -0.32, a 3-1 lead, U-21 side") == ["-0.32", "3", "1", "21"]


def test_rounding_slack_is_not_added_on_top_of_the_claim_tolerance(events):
    accuracy = FakeStats({("pass_accuracy_pct", "home", (61, 66)): 68.1})
    claims = [claim("pass_accuracy_pct", "home", (61, 66), 68.6)]     # within 0.5 of the real value
    assert codes(check(card(s("Pass accuracy was 69% after the change.", claims=claims)), events,
                       accuracy)) == ["number_mismatch"]
    assert check(card(s("Pass accuracy was 68% after the change.", claims=claims)), events, accuracy).passed


class Raising:
    def __init__(self, error):
        self.error = error

    def compute(self, ref):
        raise self.error


def test_missing_data_is_a_number_mismatch_but_a_stat_bug_is_not_swallowed(events):
    sent = card(s("Rovers had 3 shots.", claims=[claim("shots", "home", (61, 66), 3)]))
    assert codes(check(sent, events, Raising(LookupError("no data")))) == ["number_mismatch"]
    assert codes(check(sent, events, Raising(KeyError("shots")))) == ["number_mismatch"]
    with pytest.raises(ZeroDivisionError):
        check(sent, events, Raising(ZeroDivisionError("bug in the stat calculator")))


def test_claim_unit_must_be_the_stat_unit(events, stats):
    wrong_unit = Claim(value=9, unit="pct",
                       stat_ref=StatRef(metric="passes_final_third", team="home", window=(61, 66)))
    verdict = check(card(s("Final-third passes reached 9 after the change.", claims=[wrong_unit])), events, stats)
    assert codes(verdict) == ["number_mismatch"]
    assert "count" in verdict.issues[0].message


def test_digits_in_a_team_name_are_not_numbers(events, stats):
    names = {"home": "FC 1899", "away": "Harbour"}
    sent = s("FC 1899 had 9 final-third passes after the change.",
             claims=[claim("passes_final_third", "home", (61, 66), 9)])
    assert check(card(sent), events, stats, team_names=names).passed


def test_likelihood_words_are_not_direction_words_on_pivot_cards(events, stats):
    text = s("After Okafor came on at 61', Harbour City looked more likely to score.")
    assert check(card(text), events, stats).passed
