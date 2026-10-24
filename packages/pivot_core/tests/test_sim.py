"""Simulator checks. Test names carry the data-definition or QA rule they cover."""

import numpy as np
import pytest

from pivot_core.domain import MatchEvent, TrackingFrame
from pivot_core.domain.common import PITCH_LENGTH, PITCH_WIDTH
from pivot_core.sim import build_demo_match, simulate
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


@pytest.mark.xfail(reason="known issue: restart takers and receivers are teleported to the ball", strict=True)
def test_qa_003_no_teleporting_between_frames(out):
    jumps = np.hypot(*np.diff(out.frames_pos, axis=0).transpose(3, 0, 1, 2))
    assert jumps.max() <= 12.0


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
    assert 0.25 < xg_model(np.array([94.0, 34.0])) < 0.4            # around the penalty spot


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
