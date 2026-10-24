import asyncio
import json

import pytest

from pivot_core.domain import ExplanationSentence, Narrative, OutcomeDist, SimResult, ViewerPrefs
from pivot_worker import comparator as cmp
from pivot_worker.models import OfflineModelClient, ScriptedModelClient
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
    return cmp.verify_comparison(narrative, res, at_minute=62, events=EVENTS, stats=FakeStats({}), team_names=TEAMS,
                                 target_event_id="m063-s02302")


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
    assert check(narrative, result(significant)).passed


def test_template_says_it_is_a_replay_and_stays_neutral_within_noise():
    sig = cmp.template_comparison(result(True), evidence_id="m063-s02302", team_names=TEAMS)
    assert "replays" in sig.headline.lower() and "more likely" in sig.headline
    noise = cmp.template_comparison(result(False), evidence_id="m063-s02302", team_names=TEAMS)
    text = " ".join([noise.headline] + [s.text for s in noise.sentences]).lower()
    assert "replays" in noise.headline.lower()
    assert "more likely" not in text and "less likely" not in text and "win" not in text


def mixed():
    """Harbour City win clearly up; a draw down, but within noise."""
    return result(True)


def test_significance_words_are_judged_per_outcome():
    assert codes(check(card("A draw became significantly less likely."), mixed())) == ["significance_unsupported"]
    assert codes(check(card("The change mattered significantly."), mixed())) == ["significance_unsupported"]
    assert codes(check(card("A Harbour City win became significantly more likely than a draw."), mixed())) == [
        "significance_unsupported"]
    assert check(card("A Harbour City win became significantly more likely."), mixed()).passed


@pytest.mark.parametrize("text, ok", [
    ("A draw became more likely than a Harbour City win.", False),
    ("A Harbour City win became more likely than a draw.", True),
    ("A Harbour City win became more likely, and a draw less likely.", True),
    ("A draw became more likely, and a Harbour City win less likely.", False),
    ("A draw became less likely than a Harbour City win.", True),
])
def test_direction_follows_the_outcome_the_word_describes(text, ok):
    verdict = check(card(text), result())
    assert verdict.passed if ok else set(codes(verdict)) == {"direction_mismatch"}, verdict.issues


PRESS_EVENTS = {"m063-s02290": event("m063-s02290", 61, "pass"), "m063-s02310": event("m063-s02310", 63, "shot"),
                "m063-s01000": event("m063-s01000", 30, "pass")}


def test_change_press_offers_real_events_to_cite():
    _, messages = cmp.build_messages(result(), scenario_label="Press higher from 63′", target_event_id=None,
                                     at_minute=62, team_names=TEAMS, events=PRESS_EVENTS)
    offered = json.loads(messages[1]["content"])["evidence_ids"]
    assert offered and set(offered) <= {"m063-s02290", "m063-s02310"}
    narrative = cmp.template_comparison(result(), evidence_id=offered[0], team_names=TEAMS)
    assert cmp.verify_comparison(narrative, result(), at_minute=62, events=PRESS_EVENTS, stats=FakeStats({}),
                                 team_names=TEAMS, target_event_id=None).passed
    invented = card("A Harbour City win became more likely in the replays.")
    verdict = cmp.verify_comparison(invented, result(), at_minute=62, events=PRESS_EVENTS, stats=FakeStats({}),
                                    team_names=TEAMS, target_event_id=None)
    assert codes(verdict) == ["evidence_invalid"]


def test_a_moved_substitution_can_cite_the_original_event():
    late = {"m080-s03100": event("m080-s03100", 80, "substitution")}
    narrative = cmp.template_comparison(result(), evidence_id="m080-s03100", team_names=TEAMS)
    verdict = cmp.verify_comparison(narrative, result(), at_minute=74, events=late, stats=FakeStats({}),
                                    team_names=TEAMS, target_event_id="m080-s03100")
    assert verdict.passed, verdict.issues


GOOD_REPLY = json.dumps({"headline": "Keeping Moreau on protects the lead", "sentences": [
    {"text": "With Moreau on, a Harbour City win became more likely in the replays.",
     "evidence_ids": ["m063-s02302"]}]})
BAD_REPLY = GOOD_REPLY.replace("more likely", "significantly less likely")


def test_compare_retries_then_returns_the_verified_text():
    models = ScriptedModelClient(standard=[BAD_REPLY, GOOD_REPLY])
    steps = []

    async def record(step):
        steps.append(step)

    narrative = asyncio.run(cmp.compare(result(False), scenario_label="Cancel 63′ substitution",
                                  target_event_id="m063-s02302", at_minute=62, events=EVENTS, team_names=TEAMS,
                                  models=models, record=record, chain_id="whatif:1"))
    assert narrative.source == "llm" and narrative.verifier_attempts == 2
    assert [s.agent for s in steps] == ["comparator", "verifier", "comparator", "verifier"]
    assert "rejected your previous comparison" in models.calls[1][1][1]["content"]


def test_compare_falls_back_to_the_template_without_a_model():
    narrative = asyncio.run(cmp.compare(result(), scenario_label="Press higher from 63′", target_event_id=None,
                                  at_minute=62, events=PRESS_EVENTS, team_names=TEAMS, models=OfflineModelClient()))
    assert narrative.source == "template"
    assert narrative.sentences[0].evidence_ids[0] in {"m063-s02290", "m063-s02310"}
