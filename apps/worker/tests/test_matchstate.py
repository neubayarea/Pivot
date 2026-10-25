import json
from pathlib import Path

import pytest

from pivot_core.domain import MatchEvent, MinuteMetric, PivotCandidate, Substitution, TeamTactics
from pivot_core.domain.officials import FoulDetail
from pivot_worker import explainer, judge
from pivot_worker import matchstate as ms
from pivot_worker.testing import FakeStats, event

TEAMS = {"home": "Rovers", "away": "Harbour"}
RED = FoulDetail(foul_type="tackle", card="red", card_reason="professional_foul")


def match():
    evs = [
        event("m063-s00001", 0, "kickoff", tactics=TeamTactics()),
        event("m063-s00002", 0, "kickoff", team="away", tactics=TeamTactics(press="high")),
        event("m063-s00300", 20, "shot", shot_outcome="goal", xg=0.3),
        event("m063-s00700", 35, "foul", team="away", foul=RED),
        event("m063-s00701", 35, "card", team="away", foul=RED),
        event("m063-s01100", 61, "shot", team="away", shot_outcome="goal", xg=0.2),
        event("m063-s01200", 63, "substitution", tactics=TeamTactics(line_height="low", press="low"),
              substitution=Substitution(player_off_id="R-9", player_on_id="R-15", slot=9, reason="tactical")),
        event("m063-s01201", 63, "tactical_shift", tactics=TeamTactics(line_height="low", press="low",
                                                                       time_wasting=True)),
        event("m063-s01300", 68, "shot", shot_outcome="goal", xg=0.4),
    ]
    return {e.event_id: e for e in evs}


def test_score_counts_goals_up_to_the_second():
    evs = list(match().values())
    assert ms.score_at(evs, 20 * 60 + 9) == {"home": 0, "away": 0}
    assert ms.score_at(evs, 20 * 60 + 10) == {"home": 1, "away": 0}
    assert ms.score_at(evs, 90 * 60) == {"home": 2, "away": 1}


def test_a_red_card_counts_once_although_the_foul_carries_it_too():
    evs = list(match().values())
    assert ms.men_at(evs, 30 * 60) == {"home": 11, "away": 11}
    assert ms.men_at(evs, 40 * 60) == {"home": 11, "away": 10}
    second = event("m063-s00800", 50, "card", foul=RED.model_copy(update={"card": "second_yellow"}))
    assert ms.men_at([*evs, second], 60 * 60) == {"home": 10, "away": 10}


def test_match_state_around_the_window():
    metrics = [MinuteMetric(match_id="M-test", minute=m, momentum=0.5 if m < 63 else -0.1, threat_home=0,
                            threat_away=0, pressure_home=0, pressure_away=0) for m in range(40, 90)]
    state = ms.match_state(63, match(), TEAMS, before=8, after=8, metrics=metrics)
    assert state["before_window"] == {"score": "Rovers 1-0 Harbour", "men_on_pitch": {"Rovers": 11, "Harbour": 10}}
    assert state["after_window"]["score"] == "Rovers 2-1 Harbour"
    assert state["momentum_avg_10_min"] == {"before": 0.5, "after": -0.1}
    assert "momentum_avg_10_min" not in ms.match_state(63, match(), TEAMS, before=8, after=5)


def test_a_coach_decision_shows_its_tactics_and_what_they_changed():
    evs = match()
    before = ms.previous_tactics(evs)
    sub = explainer.event_line(evs["m063-s01200"], TEAMS, previous_tactics=before["m063-s01200"])
    assert sub["substitution"]["reason"] == "tactical"
    assert sub["tactics"] == {"line_height": "low", "press": "low", "width": "normal", "tempo": "normal",
                              "counter_attack": False}
    assert sub["tactics_before"] == {"line_height": "mid", "press": "mid"}
    shift = explainer.event_line(evs["m063-s01201"], TEAMS, previous_tactics=before["m063-s01201"])
    assert shift["tactics"]["time_wasting"] is True                # not a main field, but it changed
    assert shift["tactics_before"] == {"time_wasting": False}
    assert "tactics_before" not in explainer.event_line(evs["m063-s00002"], TEAMS)   # nothing before kick-off


def test_goals_carry_the_score_they_made():
    lines = {line["id"]: line for line in explainer.event_lines(list(match().values()), match(), TEAMS)}
    assert lines["m063-s01300"]["score_after"] == "Rovers 2-1 Harbour"
    assert lines["m063-s01100"]["score_after"] == "Rovers 1-1 Harbour"
    assert "score_after" not in lines["m063-s01200"]


def test_the_explainer_sees_the_match_state():
    c = PivotCandidate(match_id="M-test", minute=66, direction="home", cusum_stat=3.0, swing=0.3,
                       key_event_ids=["m063-s01300"], window=(60, 72))
    request = json.loads(explainer.build_request(c, events=match(), stats=FakeStats({}), team_names=TEAMS))
    assert request["match_state"]["before_window"]["score"] == "Rovers 1-0 Harbour"
    assert request["match_state"]["after_window"]["score"] == "Rovers 2-1 Harbour"


# --- the recorded demo (eval/fixtures/demo-1021.json, M-seed-41) ----------------------------

FIXTURE = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "demo-1021.json"


@pytest.fixture(scope="module")
def demo():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_the_demo_65_judge_request_shows_the_drop_deep_and_the_extra_man(demo):
    events = {e["event_id"]: MatchEvent.model_validate(e) for e in demo["events"]}
    metrics = [MinuteMetric.model_validate(m) for m in demo["metrics"]]
    candidate = PivotCandidate.model_validate(next(c for c in demo["candidates"] if c["minute"] == 65))
    teams = {"home": demo["match"]["home"]["name"], "away": demo["match"]["away"]["name"]}
    _, messages = judge.build_messages(candidate, events=events, metrics=metrics, stats=FakeStats({}),
                                       team_names=teams)
    request = json.loads(messages[1]["content"])
    lines = {line["id"]: line for line in request["events"]}
    assert lines["m065-s01152"]["tactics"]["line_height"] == "low"
    assert lines["m065-s01152"]["tactics_before"] == {"line_height": "mid", "press": "mid"}
    assert lines["m065-s01151"]["substitution"]["reason"] == "tactical"
    state = request["match_state"]
    assert state["before_window"] == {"score": "Harbour City 1-0 Northgate Rovers",
                                      "men_on_pitch": {"Harbour City": 11, "Northgate Rovers": 10}}
    assert state["after_window"]["score"] == "Harbour City 2-1 Northgate Rovers"   # Rovers pull one back at 69'
    assert state["momentum_avg_10_min"]["before"] > state["momentum_avg_10_min"]["after"] + 0.2   # demo seed 223: 0.24
