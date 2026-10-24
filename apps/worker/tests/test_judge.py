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


def test_parse_falls_back_to_key_events_when_every_trigger_is_invented():
    raw = json.dumps({"is_pivot": True, "severity": 3, "trigger_event_ids": ["x"], "reason": "ok"})
    assert judge.parse_verdict(raw, candidate(), set()).trigger_event_ids == ["m063-s01042"]


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
