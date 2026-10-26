"""Bx10: the comparison says why the replays differ, with numbers the Verifier checks against the result."""

import asyncio
import json

import pytest

from pivot_core.domain import (
    ArmStats, ExplanationSentence, Narrative, OutcomeDist, ScoreShare, SimResult, Spread, TeamRunStats, ViewerPrefs,
)
from pivot_worker import comparator as cmp
from pivot_worker.models import OfflineModelClient
from pivot_worker.testing import FakeStats, event

TEAMS = {"home": "Harbour City", "away": "Northvale Rovers"}
EVENTS = {"m038-s01400": event("m038-s01400", 37, "card")}
CI = {"home_win": (0.3, 0.38), "draw": (0.3, 0.4), "away_win": (0.25, 0.35)}
N = 200


def sp(mean, sd=1.0):
    return Spread(mean=mean, sd=sd, p10=0, p90=mean * 2)


def team(goals, shots, xg, possession, cards, scored, sd=None):
    sd = sd or {}
    return TeamRunStats(goals=sp(goals, 0.9), shots=sp(shots, sd.get("shots", 3.0)), shots_on_target=sp(shots / 3, 1.5),
                        xg=sp(xg, sd.get("xg", 0.5)), possession_pct=sp(possession, 3.0), cards=sp(cards, 1.0),
                        red_cards=sp(0.05, 0.2), scored_share=scored)


def arm(top, home, away):
    return ArmStats(n_runs=N, from_t=2220, top_scores=[ScoreShare(home=h, away=a, share=s) for (h, a), s in top],
                    home=home, away=away)


def result(significant=True, stats=True):
    """The demo's 38' red card taken away: Rovers keep eleven and take twice the shots."""
    base = OutcomeDist(home_win=0.83, draw=0.135, away_win=0.035, ci95=CI)
    cf = OutcomeDist(home_win=0.475, draw=0.235, away_win=0.29, ci95=CI)
    b = arm([((2, 1), 0.14), ((2, 0), 0.135)], team(1.42, 10.2, 1.41, 53, 0.9, 0.77),
            team(0.67, 5.1, 0.67, 47, 2.2, 0.52, {"shots": 2.5, "xg": 0.4}))
    c = arm([((1, 2), 0.14), ((1, 1), 0.135)], team(0.80, 7.2, 0.87, 56, 1.07, 0.55),
            team(1.40, 10.8, 1.51, 44, 2.1, 0.76, {"shots": 3.5, "xg": 0.6}))
    return SimResult(scenario_id="M-test:s1", baseline=base, counterfactual=cf,
                     baseline_stats=b if stats else None, counterfactual_stats=c if stats else None,
                     significant={"home_win": significant, "draw": False, "away_win": significant},
                     runtime_ms=900, executor="local_pool")


def card(*texts, audience="analyst"):
    return Narrative(prefs=ViewerPrefs(audience=audience), headline="A full side changes the replays", source="llm",
                     sentences=[ExplanationSentence(text=t, evidence_ids=["m038-s01400"]) for t in texts])


def check(narrative, res=None):
    return cmp.verify_comparison(narrative, res or result(), at_minute=37, events=EVENTS, stats=FakeStats({}),
                                 team_names=TEAMS, target_event_id="m038-s01400")


def codes(verdict):
    return [i.code for i in verdict.issues]


@pytest.mark.parametrize("text, issues", [
    ("Without the card, Northvale Rovers' shots rose from 5.1 to 10.8 in the replays.", []),
    ("Northvale Rovers' quality of chances rose from 0.67 to 1.51.", []),
    ("Harbour City's shots fell from 10.2 to 7.2.", []),
    ("Northvale Rovers scored at least once in 76% of the replays with the change.", []),
    ("The most common final score went from 2-1 to 1-2.", []),
    ("1-2 was the most common score with the change, in 14% of the replays.", []),
    ("A Harbour City win became less likely as Northvale Rovers' shots rose from 5.1 to 10.8.", []),
    # wrong order, team, number, direction, size, score
    ("Northvale Rovers' shots rose from 10.8 to 5.1.", ["direction_mismatch"]),
    # a number that matches nothing leaves "rose" about nothing, and the writer is told both
    ("Harbour City's shots rose from 5.1 to 10.8.", ["number_mismatch", "number_mismatch", "direction_mismatch"]),
    ("Northvale Rovers' shots rose to 12.4.", ["number_mismatch", "direction_mismatch"]),
    ("Northvale Rovers' xG was 5.1.", ["number_mismatch"]),
    ("Harbour City's shots rose from 10.2 to 7.2.", ["direction_mismatch"]),
    ("Northvale Rovers' cards fell from 2.2 to 2.1.", ["significance_unsupported"]),
    ("The most common final score went from 2-1 to 4-0.", ["number_mismatch"]),
    ("A Harbour City win became more likely as Northvale Rovers' shots rose to 10.8.", ["direction_mismatch"]),
    # the outcome percentages stay on the chart
    ("A Harbour City win fell to 48% in the replays.", ["number_mismatch"]),
])
def test_replay_numbers_are_checked_against_the_result(text, issues):
    assert codes(check(card(text))) == issues


def test_fans_get_one_number_a_sentence():
    assert check(card("Northvale Rovers' shots rose to 10.8 on average.", audience="fan")).passed
    assert codes(check(card("Northvale Rovers' shots rose from 5.1 to 10.8.", audience="fan"))) == ["number_mismatch"]
    assert check(card("The most common final score went from 2-1 to 1-2.", audience="fan")).passed   # scores are not counts


def test_an_old_result_still_allows_no_numbers():
    assert codes(check(card("Northvale Rovers' shots rose from 5.1 to 10.8."), result(stats=False))) == [
        "number_mismatch", "number_mismatch", "direction_mismatch"]
    assert cmp.replay_facts(result(stats=False)) is None and cmp.reasons(result(stats=False), TEAMS) == []


def test_stat_changes_say_which_are_clear():
    rows = {(d["team"], d["stat"]): d for d in cmp.stat_changes(result())}
    assert rows[("away", "shots")] | {"_size": 0} == {"team": "away", "stat": "shots", "baseline": 5.1,
                                                      "with_change": 10.8, "clear": True, "_raw": (5.1, 10.8),
                                                      "_size": 0}
    assert not rows[("away", "cards")]["clear"]              # 2.2 -> 2.1 with a spread of 1 is noise
    assert rows[("away", "scored_pct")]["clear"] and rows[("away", "scored_pct")]["with_change"] == 76
    assert cmp.stat_changes(result())[0]["clear"]


def test_the_prompt_gets_the_replay_numbers():
    prompt, messages = cmp.build_messages(result(), scenario_label="Remove 38′ red card", target_event_id="m038-s01400",
                                          at_minute=37, team_names=TEAMS, events=EVENTS)
    request = json.loads(messages[1]["content"])
    assert request["replay_numbers"]["baseline"]["top_scores"][0] == {"score": "2-1", "share_pct": 14}
    assert request["replay_numbers"]["with_change"]["away"]["shots"] == 10.8
    assert {"team": "away", "stat": "shots", "baseline": 5.1, "with_change": 10.8, "clear": True} in request["stat_changes"]
    assert "replay_numbers" in prompt.text and "Write no numbers" not in prompt.text and "{{" not in prompt.text
    old, messages = cmp.build_messages(result(stats=False), scenario_label="x", target_event_id=None, at_minute=37,
                                       team_names=TEAMS)
    assert "Write no numbers" in old.text and "replay_numbers" not in messages[1]["content"]


def test_the_template_gives_the_reasons():
    narrative = cmp.template_comparison(result(), evidence_id="m038-s01400", team_names=TEAMS)
    assert [s.text for s in narrative.sentences] == [
        "With the change, a Harbour City win became less likely in the replays.",
        "As played, the most common final score was 2-1; with the change it was 1-2.",
        "From that moment, Northvale Rovers' shots rose from 5.1 to 10.8 on average.",
    ]
    assert check(narrative).passed


@pytest.mark.parametrize("lang", ["en", "zh", "es"])
@pytest.mark.parametrize("audience", ["analyst", "fan"])
@pytest.mark.parametrize("significant", [True, False])
def test_the_template_passes_the_verifier_in_every_language(lang, audience, significant):
    prefs = ViewerPrefs(language=lang, audience=audience)
    res = result(significant)
    narrative = cmp.template_comparison(res, evidence_id="m038-s01400", team_names=TEAMS, prefs=prefs)
    assert len(narrative.sentences) == 3
    assert "1-2" in narrative.sentences[1].text and "10.8" in narrative.sentences[2].text
    verdict = cmp.verify_comparison(narrative, res, at_minute=37, events=EVENTS, stats=FakeStats({}),
                                    team_names=TEAMS, target_event_id="m038-s01400")
    assert verdict.passed, (narrative.sentences, verdict.issues)


def test_the_template_names_no_change_that_is_noise():
    res = result()
    res = res.model_copy(update={"counterfactual_stats": res.baseline_stats})     # the same numbers in both groups
    for lang in ("en", "zh", "es"):
        narrative = cmp.template_comparison(res, evidence_id="m038-s01400", team_names=TEAMS,
                                            prefs=ViewerPrefs(language=lang))
        assert len(narrative.sentences) == 2 and "2-1" in narrative.sentences[1].text
        verdict = cmp.verify_comparison(narrative, res, at_minute=37, events=EVENTS, stats=FakeStats({}),
                                        team_names=TEAMS, target_event_id="m038-s01400")
        assert verdict.passed, (narrative.sentences, verdict.issues)
    assert narrative.sentences[1].text == "El resultado final más repetido fue 2-1 con y sin el cambio."


def test_the_fake_pipeline_explains_with_the_new_numbers():
    narrative = asyncio.run(cmp.compare(result(), scenario_label="Remove 38′ red card", target_event_id="m038-s01400",
                                        at_minute=37, events=EVENTS, team_names=TEAMS, models=OfflineModelClient()))
    assert narrative.source == "template" and "10.8" in narrative.sentences[2].text
