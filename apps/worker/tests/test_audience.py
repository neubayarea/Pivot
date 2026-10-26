import json
import re

import pytest

from pivot_core.domain import ExplanationSentence, Narrative, PivotCandidate, ViewerPrefs
from pivot_worker import explainer as ex
from pivot_worker.template import template_explain
from pivot_worker.testing import event
from pivot_worker.verifier import verify
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


def test_ax49_a_picked_team_owns_the_headline_and_a_fan_hears_a_supporter():
    analyst = ex.audience_brief(ViewerPrefs(focus_team="away"), TEAMS)
    fan = ex.audience_brief(ViewerPrefs(audience="fan", focus_team="away"), TEAMS)
    neutral_fan = ex.audience_brief(FAN, TEAMS)
    assert "The headline is about Harbour too" in analyst and "never as the other side's win" in analyst
    assert "Harbour supporters would feel it" in fan and "supporters would feel" not in analyst
    assert "feeling of the moment" in neutral_fan and "feeling" not in ex.audience_brief(ViewerPrefs(), TEAMS)


@pytest.mark.parametrize("side,headline", [("home", "Momentum swings to Rovers"), ("away", "Harbour lose their grip")])
def test_ax49_template_headline_takes_the_picked_teams_side(events, stats, side, headline):
    for audience in ("analyst", "fan"):
        prefs = ViewerPrefs(audience=audience, focus_team=side)
        narrative = template_explain(candidate(), events=events, stats=stats, team_names=TEAMS, prefs=prefs)
        assert narrative.headline == headline
        assert verify(narrative, pivot_minute=63, events=events, stats=stats).passed
    # No team picked: the headline still names the event that set it off.
    assert template_explain(candidate(), events=events, stats=stats, team_names=TEAMS).headline != headline


def test_fan_versions_may_not_use_jargon(events, stats):
    def card(prefs):
        return Narrative(prefs=prefs, headline="Rovers take over", source="llm", sentences=[
            ExplanationSentence(text="Rovers moved into the half-space and pressed.", evidence_ids=["m063-s01042"])])

    assert verify(card(ViewerPrefs()), pivot_minute=63, events=events, stats=stats).passed
    verdict = verify(card(FAN), pivot_minute=63, events=events, stats=stats)
    assert [i.code for i in verdict.issues] == ["banned_term"] and "everyday words" in verdict.issues[0].message


@pytest.mark.parametrize("prefs", ex.DEFAULT_VERSIONS)
def test_template_versions_pass_for_both_audiences(events, stats, prefs):
    narrative = template_explain(candidate(), events=events, stats=stats, team_names=TEAMS, prefs=prefs)
    assert narrative.prefs == prefs
    assert verify(narrative, pivot_minute=63, events=events, stats=stats).passed
    text = " ".join(s.text for s in narrative.sentences)
    if prefs.audience == "fan":
        assert "danger created" in text
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
