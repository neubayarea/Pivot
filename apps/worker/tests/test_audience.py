import json
import re

import pytest

from pivot_core.domain import ExplanationSentence, Narrative, PivotCandidate, ViewerPrefs
from pivot_worker import explainer as ex
from pivot_worker.template import template_explain
from pivot_worker.testing import FakeStats, event
from pivot_worker.verifier import numbers_in, verify
from pivot_worker.vocabulary import JARGON

TEAMS = {"home": "Rovers", "away": "Harbour"}
FAN = ViewerPrefs(audience="fan")


def candidate():
    return PivotCandidate(match_id="M-test", minute=63, direction="home", cusum_stat=4.2, swing=0.3,
                          key_event_ids=["m063-s01042"], window=(58, 68))


def test_default_versions_are_one_per_audience():
    assert [p.audience for p in ex.DEFAULT_VERSIONS] == ["analyst", "fan"]


def test_fan_and_analyst_prompts_differ():
    analyst = ex.system_prompt(ViewerPrefs(), TEAMS).text
    fan = ex.system_prompt(FAN, TEAMS).text
    assert "mechanism" in analyst and "short story" in fan
    assert "Okafor changes the game for Rovers" in fan and "Okafor changes the game" not in analyst
    assert "| passes into the attacking third |" in fan


def test_focus_team_and_player_shape_the_prompt_and_the_sheet(events, stats):
    evs = {**events, "m063-s01080": event("m063-s01080", 62, player_id="rov-9")}
    prefs = ViewerPrefs(focus_team="away", focus_player_id="rov-9")
    prompt, messages = ex.build_messages(candidate(), events=evs, stats=stats, team_names=TEAMS, prefs=prefs,
                                         player_names={"rov-9": "Okafor"})
    assert "Harbour's point of view" in prompt.text and "follows Okafor (`rov-9`)" in prompt.text
    request = json.loads(messages[1]["content"])
    player_rows = [c for c in request["stat_sheet"] if c["stat_ref"]["player_id"] == "rov-9"]
    assert len(player_rows) == len(ex.PLAYER_METRICS) * 2 and player_rows[0]["stat_ref"]["team"] == "home"
    assert {"id": "m063-s01080", "player": "Okafor"}.items() <= next(
        e for e in request["events"] if e["id"] == "m063-s01080").items()


def test_fan_versions_may_not_use_jargon(events, stats):
    def card(prefs):
        return Narrative(prefs=prefs, headline="Rovers take over", source="llm", sentences=[
            ExplanationSentence(text="Rovers moved into the half-space and pressed.", evidence_ids=["m063-s01042"])])

    assert verify(card(ViewerPrefs()), pivot_minute=63, events=events, stats=stats).passed
    verdict = verify(card(FAN), pivot_minute=63, events=events, stats=stats)
    assert [i.code for i in verdict.issues] == ["banned_term"] and "everyday words" in verdict.issues[0].message


@pytest.mark.parametrize("prefs", ex.DEFAULT_VERSIONS)
def test_template_versions_pass_for_both_audiences(events, stats, prefs):
    if prefs.audience == "fan":                   # something a fan can count changed too (#242)
        stats = FakeStats({**stats.values, ("shots", "home", (58, 63)): 1, ("shots", "home", (63, 68)): 4})
    narrative = template_explain(candidate(), events=events, stats=stats, team_names=TEAMS, prefs=prefs)
    assert narrative.prefs == prefs
    assert verify(narrative, pivot_minute=63, events=events, stats=stats).passed
    text = " ".join(s.text for s in narrative.sentences)
    if prefs.audience == "fan":
        assert "Rovers' shots rose to 4" in text and "threat" not in text and "danger" not in text
        assert all(len(numbers_in(s.text, "en")) <= 1 for s in narrative.sentences)
        assert not any(re.search(rf"\b{re.escape(j.lower())}\b", text.lower()) for j in JARGON)
    else:
        assert "threat created" in text


def test_comparator_uses_the_same_audience_modes():
    from pivot_core.domain import OutcomeDist, SimResult
    from pivot_worker import comparator

    ci = {"home_win": (0.3, 0.4), "draw": (0.3, 0.4), "away_win": (0.2, 0.3)}
    dist = OutcomeDist(home_win=0.35, draw=0.35, away_win=0.3, ci95=ci)
    result = SimResult(scenario_id="s", baseline=dist, counterfactual=dist, significant={}, runtime_ms=1,
                       executor="local_pool")
    fan = comparator.system_prompt(result, ViewerPrefs(audience="fan", focus_team="home"), TEAMS).text
    assert "short story" in fan and "Rovers' point of view" in fan
