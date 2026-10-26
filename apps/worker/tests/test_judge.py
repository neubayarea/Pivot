import json

import pytest
from pydantic import ValidationError

from pivot_core.domain import MinuteMetric, PivotCandidate
from pivot_worker import judge
from pivot_worker.testing import event

TEAMS = {"home": "Rovers", "away": "Harbour"}


def candidate(swing=0.3, key=("m063-s01042",)):
    return PivotCandidate(match_id="M-test", minute=63, direction="home", cusum_stat=4.2, swing=swing,
                          key_event_ids=list(key), window=(58, 68))


def metrics():
    return [MinuteMetric(match_id="M-test", minute=m, momentum=0.1, threat_home=0, threat_away=0,
                         pressure_home=0, pressure_away=0) for m in range(50, 80)]


def test_prompt_is_complete_and_hashed():
    prompt = judge.system_prompt()
    assert "{{" not in prompt.text and '"is_pivot"' in prompt.text
    assert prompt.hash == judge.system_prompt().hash


def test_request_uses_eight_minutes_either_side(events, stats):
    evs = {**events, "m063-s01300": event("m063-s01300", 70)}
    _, messages = judge.build_messages(candidate(), events=evs, metrics=metrics(), stats=stats, team_names=TEAMS)
    request = json.loads(messages[1]["content"])
    assert [m["minute"] for m in request["momentum_by_minute"]] == list(range(55, 72))
    assert "m063-s01300" in [e["id"] for e in request["events"]]        # +7 min: Judge sees it, Explainer would not
    assert {c["stat_ref"]["metric"] for c in request["stats"]} == set(judge.JUDGE_METRICS)


def test_parse_keeps_real_triggers_and_drops_invented_ones():
    raw = {"is_pivot": True, "severity": 2, "trigger_event_ids": ["m063-s01042", "made-up"], "reason": "ok"}
    v = judge.parse_verdict(raw, candidate(), {"m063-s01042"})
    assert v.trigger_event_ids == ["m063-s01042"]


def test_more_than_three_triggers_keeps_the_first_three_real_ones():
    raw = json.dumps({"is_pivot": True, "severity": 2, "reason": "ok",
                      "trigger_event_ids": ["made-up", "a", "b", "c", "d"]})
    assert judge.parse_verdict(raw, candidate(), {"a", "b", "c", "d"}).trigger_event_ids == ["a", "b", "c"]


@pytest.mark.parametrize("triggers", [["x"], []])
def test_a_yes_with_no_real_trigger_is_not_accepted(triggers):
    raw = json.dumps({"is_pivot": True, "severity": 3, "trigger_event_ids": triggers, "reason": "ok"})
    with pytest.raises(judge.InvalidVerdict):
        judge.parse_verdict(raw, candidate(), set())


def test_triggers_must_be_events_the_judge_was_shown(events):
    far = {**events, "m063-s00100": events["m063-s00100"]}          # minute 20: in the match, not the window
    shown = {e.event_id for e in judge.judge_events(candidate(), far)}
    assert "m063-s00100" not in shown and "m063-s01042" in shown
    raw = {"is_pivot": True, "severity": 2, "trigger_event_ids": ["m063-s00100", "m063-s01042"], "reason": "ok"}
    assert judge.parse_verdict(raw, candidate(), shown).trigger_event_ids == ["m063-s01042"]
    with pytest.raises(judge.InvalidVerdict):
        judge.parse_verdict({**raw, "trigger_event_ids": ["m063-s00100"]}, candidate(), shown)


def test_request_explains_the_momentum_sign(events, stats):
    _, messages = judge.build_messages(candidate(), events=events, metrics=metrics(), stats=stats, team_names=TEAMS)
    assert json.loads(messages[1]["content"])["momentum_sign"] == "above 0: Rovers on top; below 0: Harbour on top"
    assert "below 0 means the away team" in messages[0]["content"]


def test_examples_look_like_real_requests(events, stats):
    _, messages = judge.build_messages(candidate(), events=events, metrics=metrics(), stats=stats, team_names=TEAMS)
    real = json.loads(messages[1]["content"])
    for request, verdict in judge.EXAMPLES:
        assert request.keys() == real.keys() and request["alarm"].keys() == real["alarm"].keys()
        assert request["stats"][0].keys() == real["stats"][0].keys()
        m = request["alarm"]["minute"]
        assert [x["minute"] for x in request["momentum_by_minute"]] == list(range(m - 8, m + 9))
        assert {tuple(c["stat_ref"]["window"]) for c in request["stats"]} == {(m - 5, m), (m, m + 5)}
        assert set(verdict.trigger_event_ids) <= {e["id"] for e in request["events"]}
        assert json.dumps(request, ensure_ascii=False) in judge.system_prompt().text
    assert any(r["alarm"]["swing"] < 0 and v.is_pivot for r, v in judge.EXAMPLES)   # one pivot towards the away side


def test_a_no_carries_no_triggers():
    raw = {"is_pivot": False, "severity": 1, "trigger_event_ids": ["m063-s01042"], "reason": "noise"}
    assert judge.parse_verdict(raw, candidate(), {"m063-s01042"}).trigger_event_ids == []


def test_parse_rejects_bad_shapes():
    with pytest.raises(ValidationError):
        judge.parse_verdict({"is_pivot": True, "severity": 4, "trigger_event_ids": [], "reason": ""}, candidate(), set())
    with pytest.raises(ValidationError):
        judge.parse_verdict('{"is_pivot": "maybe"}', candidate(), set())


@pytest.mark.parametrize("swing,severity", [(0.1, 1), (-0.35, 2), (0.6, 3)])
def test_fallback_severity_follows_the_swing(swing, severity):
    v = judge.fallback_verdict(candidate(swing=swing))
    assert v.is_pivot and v.severity == severity and v.trigger_event_ids == ["m063-s01042"]


def test_make_pivot():
    p = judge.make_pivot(candidate(), judge.fallback_verdict(candidate()), chain_id="c1", status="degraded")
    assert p.pivot_id == "M-test:p63" and p.status == "degraded" and p.narrative is None
