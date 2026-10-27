"""Per-minute momentum, the Opta way (MET-024, ADR-0010), and the turning points on recorded matches."""

import json
from pathlib import Path

import pytest

from pivot_core.analytics import detect_candidates, momentum_series, severity
from pivot_core.analytics.momentum import CAP, HALF_LIFE_MIN, possession_value
from pivot_core.domain import MatchEvent
from pivot_core.domain.common import PITCH_LENGTH, PITCH_WIDTH

MID = "M-test"
DECAY = 0.5 ** (1 / HALF_LIFE_MIN)
GOAL = (PITCH_LENGTH - 1, PITCH_WIDTH / 2)          # right in front of the away goal: far above the cap
MIDFIELD = (PITCH_LENGTH / 2, PITCH_WIDTH / 2)
FIXTURE = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "demo-1021.json"
# a recorded match that never changes (eval/frozen/README.md), for checks on one specific match
FROZEN = Path(__file__).resolve().parents[3] / "eval" / "frozen" / "m-seed-29-before-ax44.json"

_seq = iter(range(1, 100_000))


def act(minute, team="home", type_="pass", at=MIDFIELD, to=None, outcome="success", period=1, second=5, threat=0.0):
    n = next(_seq)
    t = minute * 60 + second
    start = {1: 0, 2: 47 * 60}.get(period, t - 5)
    if team == "away":                               # same spot as seen by the away side attacking right to left
        at = (PITCH_LENGTH - at[0], PITCH_WIDTH - at[1])
        to = None if to is None else (PITCH_LENGTH - to[0], PITCH_WIDTH - to[1])
    return MatchEvent(match_id=MID, seq=n, event_id=f"e{n}", t=t, period=period, period_t=t - start, type=type_,
                      team=team, location=at, end_location=to, outcome=outcome, threat=threat)


def momentum(events):
    return {m.minute: m.momentum for m in momentum_series(MID, events)}


def test_met_024_a_team_minute_counts_its_best_action_only():
    one = momentum([act(3, at=GOAL)])
    many = momentum([act(3, at=GOAL)] + [act(3, second=10 + i) for i in range(20)])     # lots of passing in midfield
    assert many[3] == one[3]


def test_met_024_the_peak_is_capped():
    assert possession_value(act(0, at=GOAL)) > 2 * CAP
    near = (PITCH_LENGTH - 10, PITCH_WIDTH / 2)            # about at the cap
    assert momentum([act(3, at=GOAL)])[3] == momentum([act(3, at=near)])[3] == round(1 - DECAY, 4)


def test_met_024_a_successful_action_counts_where_it_ends_and_a_lost_ball_subtracts_nothing():
    to_goal = momentum([act(3, to=GOAL)])
    lost = momentum([act(3, to=GOAL, outcome="fail")])
    assert to_goal[3] == round(1 - DECAY, 4)
    assert 0 < lost[3] < 0.1                                # only where it started, and not below zero
    assert momentum([act(3, to=GOAL), act(3, second=30, outcome="fail")])[3] == to_goal[3]


def test_met_024_home_minus_away_between_minus_one_and_one():
    both = momentum([act(3, at=GOAL), act(3, team="away", at=GOAL)])
    assert both[3] == 0
    away = momentum([act(3, team="away", at=GOAL)])
    assert away[3] == -round(1 - DECAY, 4)
    pinned = momentum([act(m, at=GOAL) for m in range(40)])
    assert 0.99 < pinned[39] <= 1


def test_met_024_recent_minutes_weigh_most():
    m = momentum([act(3, at=GOAL), act(10)])
    assert m[3] == round(1 - DECAY, 4)
    assert m[3 + 3] == pytest.approx(m[3] * 0.25, abs=1e-3)            # two half-lives later
    # one peak 4 minutes ago weighs about 1/6 of one now
    assert 0.15 < 0.5 ** (4 / HALF_LIFE_MIN) < 0.2


def test_met_024_both_sides_restart_at_the_start_of_each_period():
    first = [act(m, at=GOAL) for m in range(40, 47)]
    second = [act(47, team="away", period=2, at=GOAL)]
    m = momentum(first + second)
    assert m[46] > 0.9
    assert m[47] == -round(1 - DECAY, 4)                    # nothing carried over from the first half


def test_met_024_threat_columns_keep_the_sum_of_threat_added():
    metrics = momentum_series(MID, [act(3, threat=0.02), act(3, second=20, threat=-0.01),
                                    act(3, team="away", threat=0.05)])
    assert (metrics[3].threat_home, metrics[3].threat_away) == (0.01, 0.05)


def test_met_024_shootout_minutes_are_left_out():
    events = [act(3, at=GOAL), act(130, period=5, team="away", at=GOAL)]
    assert max(momentum(events)) == 3


@pytest.fixture(scope="module")
def demo():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    events = [MatchEvent.model_validate(e) for e in data["events"]]
    return data, events


def test_b02_demo_metrics_and_candidates_are_the_ones_the_code_gives(demo):
    data, events = demo
    metrics = momentum_series(data["match"]["match_id"], events)
    assert [m.model_dump(mode="json") for m in metrics] == data["metrics"]
    cands = detect_candidates(data["match"]["match_id"], metrics, events)
    assert [c.model_dump(mode="json", round_trip=True) for c in cands] == data["candidates"]


def test_b06_red_card_and_planted_substitution_are_turning_points_in_the_frozen_match():
    """On the frozen match (eval/frozen, the demo before Ax44) the detector, as it is now, still finds
    the red card and the planted substitution."""
    data = json.loads(FROZEN.read_text(encoding="utf-8"))
    events = [MatchEvent.model_validate(e) for e in data["events"]]
    red = next(e for e in events if e.type == "card" and e.foul and e.foul.card == "red")
    sub = next(e for e in events if e.type == "substitution" and e.substitution.reason == "tactical"
               and e.team == "home")
    metrics = momentum_series(data["match"]["match_id"], events)
    cands = [c.model_dump(mode="json") for c in detect_candidates(data["match"]["match_id"], metrics, events)]
    # Rovers (away) down to ten: momentum turns towards Harbour City (home) ...
    assert any(c["direction"] == "home" and red.minute - 2 <= c["minute"] <= red.minute + 4
               and red.event_id in c["key_event_ids"] for c in cands)
    # ... and Harbour City sit deeper after their substitution: it turns towards Rovers
    assert any(c["direction"] == "away" and sub.minute - 2 <= c["minute"] <= sub.minute + 6
               and sub.event_id in c["key_event_ids"] for c in cands)


@pytest.mark.parametrize("swing,expected", [(0.2, 1), (-0.32, 2), (0.42, 3)])
def test_b06_severity_cut_offs_are_on_the_opta_scale(swing, expected):
    assert severity(swing, [], {}) == expected
