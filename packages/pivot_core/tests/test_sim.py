"""Simulator checks. Test names carry the data-definition or QA rule they cover."""

import numpy as np
import pytest

from pivot_core.domain import MatchEvent, TrackingFrame
from pivot_core.domain.common import PITCH_LENGTH, PITCH_WIDTH
from pivot_core.sim import DEMO_1021, build_demo_match, simulate
from pivot_core.sim.engine import xg_model
from pivot_core.sim.movement import MovementModel, TeamShape, to_view


@pytest.fixture(scope="module")
def out():
    return simulate(build_demo_match(1021))


def test_same_seed_same_match():
    a = simulate(build_demo_match(7))
    b = simulate(build_demo_match(7))
    assert [e["event_id"] for e in a.events] == [e["event_id"] for e in b.events]
    assert np.array_equal(a.frames_pos, b.frames_pos)


def test_events_and_frames_match_the_data_format(out):
    events = out.events_as_models()
    frames = out.frames_as_models()
    assert all(isinstance(e, MatchEvent) for e in events)
    assert all(isinstance(f, TrackingFrame) for f in frames)


def test_qa_001_time_and_seq_increase(out):
    t = [e["t"] for e in out.events]
    seq = [e["seq"] for e in out.events]
    assert t == sorted(t)
    assert seq == list(range(1, len(seq) + 1))


def test_qa_002_one_frame_per_second(out):
    assert np.array_equal(out.frames_t, np.arange(out.frames_t[0], out.frames_t[-1] + 1))


def test_qa_003_running_speed_is_human(out):
    assert out.frames_speed.max() <= 12.0


def jump_share(out) -> float:
    """Share of one-second steps longer than 12 m, same player in the same slot and period."""
    jumps = np.hypot(*np.diff(out.frames_pos, axis=0).transpose(3, 0, 1, 2))
    same_period = out.frames_period[1:] == out.frames_period[:-1]
    same_player = np.array([[[a == b for a, b in zip(x[k], y[k])] for k in (0, 1)]
                            for x, y in zip(out.frames_ids, out.frames_ids[1:])])
    return float(np.mean(jumps[same_period[:, None, None] & same_player] > 12.0))


def test_qa_003_no_teleporting_between_frames_except_at_half_time(out):
    assert jump_share(out) < 1e-4                         # at most a stray jump from an interception


def test_qa_005_score_equals_goals(out):
    goals = {"home": 0, "away": 0}
    for e in out.events:
        if e["type"] == "shot" and e["shot_outcome"] == "goal":
            goals[e["team"]] += 1
    assert (goals["home"], goals["away"]) == (out.match.score.home, out.match.score.away)


def test_qa_006_players_on_pitch_between_7_and_11(out):
    for ids in out.frames_ids:
        for team in ids:
            assert 7 <= sum(p is not None for p in team) <= 11


def test_qa_008_links_are_both_ways(out):
    by_id = {e["event_id"]: e for e in out.events}
    for e in out.events:
        for other in e.get("related_event_ids", []):
            assert e["event_id"] in by_id[other].get("related_event_ids", [])


def test_positions_stay_on_the_pitch(out):
    x, y = out.frames_pos[..., 0], out.frames_pos[..., 1]
    assert x.min() >= 0 and x.max() <= PITCH_LENGTH and y.min() >= 0 and y.max() <= PITCH_WIDTH


def test_attr_008_xg_falls_with_distance_and_headers():
    assert xg_model(np.array([99.0, 34.0])) > xg_model(np.array([88.0, 34.0])) > xg_model(np.array([80.0, 34.0]))
    assert xg_model(np.array([95.0, 34.0]), header=True) < xg_model(np.array([95.0, 34.0]))
    assert 0.15 < xg_model(np.array([94.0, 34.0])) < 0.35           # open play from the spot: public models 0.15-0.3


def test_b11_low_line_sits_deeper_than_high_line():
    m = build_demo_match(3)
    sheet = m.home.sheet
    pace = {p.player_id: 0.7 for p in m.home.squad}
    lows, highs = [], []
    for line in ("low", "high"):
        tactics = m.home.tactics.model_copy(update={"line_height": line})
        shape = TeamShape.from_sheet(0, sheet, tactics, pace)
        other = TeamShape.from_sheet(1, m.away.sheet, m.away.tactics, {p.player_id: 0.7 for p in m.away.squad})
        model = MovementModel(np.random.default_rng(0))
        pos = np.zeros((2, 11, 2))
        pos[0] = shape.anchors
        pos[1] = to_view(other.anchors, 1)
        targets = model.targets(0, (shape, other), pos, np.array([60.0, 34.0]), 1, (1, 9), False, (-99, -99), None)
        back = [targets[0, i, 0] for i, r in enumerate(shape.roles) if r in ("CB",)]
        (lows if line == "low" else highs).append(np.mean(back))
    assert lows[0] < highs[0] - 10

@pytest.fixture(scope="module")
def planted_out():
    return simulate(DEMO_1021.build(), plants=list(DEMO_1021.plants))


@pytest.fixture(scope="module")
def planted(planted_out):
    return planted_out.events_as_models()


def test_qa_003_players_keep_their_place_when_the_shape_changes(planted_out):
    # the red card and the 63' change both move players to new slots in the team sheet
    assert jump_share(planted_out) < 1e-4


def test_b04_planted_red_card_lands_just_after_the_minute(planted):
    reds = [e for e in planted if e.type == "card" and e.foul.card == "red"]
    assert reds and reds[0].team == "away"
    assert reds[0].clock_label in ("38'", "39'", "40'")               # plants follow the scoreboard clock


def test_b04_planted_substitution_and_tactics_change_at_the_next_dead_ball(planted):
    sub = next(e for e in planted if e.type == "substitution" and e.substitution.reason == "tactical")
    assert sub.period == 2 and 18 * 60 <= sub.period_t < 21 * 60             # 63' to 66' on the clock
    assert (sub.substitution.player_off_id, sub.substitution.player_on_id) == ("h09", "h15")
    shift = next(e for e in planted if e.type == "tactical_shift" and e.team == "home" and e.t >= sub.t)
    assert shift.tactics.line_height == "low" and shift.tactics.press == "low"
    later = [e for e in planted if e.t > sub.t and e.player_id == "h09"]
    assert later == []                                     # the player taken off does nothing more


def test_b04_ten_men_drop_a_forward_and_keep_four_at_the_back(planted):
    red = next(e for e in planted if e.type == "card" and e.foul.card == "red")
    shift = next(e for e in planted if e.type == "tactical_shift" and e.team == red.team and e.t >= red.t)
    roles = [s.role for s in shift.team_sheet.starters]
    assert len(roles) == 10 and shift.team_sheet.formation == "4-4-2"
    assert sum(r in ("LB", "CB", "RB", "LWB", "RWB") for r in roles) == 4


def test_b02_demo_preset_is_labelled_and_repeatable():
    m = DEMO_1021.build()
    assert m.preset == "demo-1021"
    a = simulate(m, plants=list(DEMO_1021.plants))
    b = simulate(DEMO_1021.build(), plants=list(DEMO_1021.plants))
    assert a.match.score == b.match.score and len(a.events) == len(b.events)
