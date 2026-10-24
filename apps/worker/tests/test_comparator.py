import json

import pytest

from pivot_core.domain import ExplanationSentence, Narrative, OutcomeDist, SimResult, ViewerPrefs
from pivot_worker import comparator as cmp
from pivot_worker.testing import FakeStats, event

TEAMS = {"home": "Harbour City", "away": "Northvale Rovers"}
EVENTS = {"m063-s02302": event("m063-s02302", 62, "substitution")}
CI = {"home_win": (0.3, 0.38), "draw": (0.3, 0.4), "away_win": (0.25, 0.35)}


def result(significant=True):
    base = OutcomeDist(home_win=0.34, draw=0.36, away_win=0.30, ci95=CI)
    cf = OutcomeDist(home_win=0.52, draw=0.28, away_win=0.20, ci95=CI)
    return SimResult(scenario_id="M-test:s1", baseline=base, counterfactual=cf,
                     significant={"home_win": significant, "draw": False, "away_win": False},
                     runtime_ms=900, executor="local_pool")


def card(*texts):
    return Narrative(prefs=ViewerPrefs(), headline="Keeping Moreau on protects the lead", source="llm",
                     sentences=[ExplanationSentence(text=t, evidence_ids=["m063-s02302"]) for t in texts])


def check(narrative, res):
    return cmp.verify_comparison(narrative, res, at_minute=62, events=EVENTS, stats=FakeStats({}), team_names=TEAMS)


def codes(verdict):
    return [i.code for i in verdict.issues]


def test_the_example_passes():
    narrative = Narrative(prefs=ViewerPrefs(), source="llm", **cmp.EXAMPLE.model_dump())
    assert check(narrative, result()).passed


def test_likelihood_words_must_match_the_named_outcome():
    assert check(card("A Harbour City win became more likely."), result()).passed
    assert codes(check(card("A Harbour City win became less likely."), result())) == ["direction_mismatch"]
    assert codes(check(card("A draw became more likely."), result())) == ["direction_mismatch"]
    assert codes(check(card("Things became more likely."), result())) == ["direction_mismatch"]


def test_significance_wording_follows_the_intervals():
    text = "A Harbour City win became significantly more likely."
    assert check(card(text), result(significant=True)).passed
    assert codes(check(card(text), result(significant=False))) == ["significance_unsupported"]


def test_numbers_are_not_allowed_in_comparisons():
    assert codes(check(card("A Harbour City win rose to 52%."), result())) == ["number_mismatch"]


def test_prompt_reflects_significance():
    prompt, messages = cmp.build_messages(result(False), scenario_label="Cancel 63′ substitution",
                                          target_event_id="m063-s02302", at_minute=62, team_names=TEAMS)
    assert "{{" not in prompt.text and "within noise" in prompt.text
    assert json.loads(messages[1]["content"])["change"]["home_win"] == 0.18
    sig, _ = cmp.build_messages(result(True), scenario_label="x", target_event_id=None, at_minute=62, team_names=TEAMS)
    assert "do not overlap: home_win" in sig.text and sig.hash != prompt.hash


@pytest.mark.parametrize("significant", [True, False])
def test_template_comparison_passes_the_verifier(significant):
    narrative = cmp.template_comparison(result(significant), evidence_id="m063-s02302", team_names=TEAMS)
    assert narrative.source == "template"
    assert narrative.headline == "Harbour City win becomes more likely"
    assert check(narrative, result(significant)).passed
