"""B12 realism rules: game state, team strength, formations. Test names carry the definition they cover."""

import numpy as np
import pytest

from pivot_core.domain.common import PITCH_LENGTH
from pivot_core.sim import build_demo_match, simulate
from pivot_core.sim.engine import Engine, xg_model
from pivot_core.sim.movement import MovementModel, TeamShape, to_view


def engine_at(minute: int, score: tuple[int, int], seed: int = 7) -> Engine:
    """An engine whose clock shows `minute` in the second half with the given score."""
    e = Engine(build_demo_match(seed), seed)
    e.period, e.period_start, e.t = 2, 0, (minute - 45) * 60
    e.score = list(score)
    e._update_state()
    return e


def test_real_001_leading_side_drops_off_and_trailing_side_pushes_late_on():
    e = engine_at(80, (1, 0))
    assert e.urgency[0] < 0 < e.urgency[1]
    assert e.move.line_shift[0] < 0 < e.move.line_shift[1]
    assert e.move.press_shift == [-1, 1]                    # a one-goal game in the last ten minutes
    level = engine_at(80, (1, 1))
    assert level.urgency == [0.0, 0.0] and level.move.line_shift == [0.0, 0.0]


def test_real_001_score_matters_more_as_the_clock_runs_down():
    assert engine_at(50, (0, 1)).urgency[0] < engine_at(85, (0, 1)).urgency[0]
    e = Engine(build_demo_match(7), 7)
    e.score = [2, 0]
    e.t = 20 * 60
    e._update_state()
    assert e.urgency == [0.0, 0.0]                            # nothing changes in the first half hour


def test_real_001_a_lost_cause_is_chased_less_than_a_one_goal_game():
    assert 0 < engine_at(80, (0, 3)).urgency[0] < engine_at(80, (0, 1)).urgency[0]


def test_real_002_a_side_a_man_short_drops_deeper():
    e = engine_at(50, (0, 0))
    e.shapes[1].player_ids[5] = None
    e._update_state()
    assert e.move.line_shift[1] < 0 < e.move.line_shift[0]


def test_real_001_leading_side_takes_its_time_over_restarts():
    lead, level = engine_at(85, (1, 0)), engine_at(85, (0, 0))
    for e in (lead, level):
        e._set_restart("goal_kick", 0, np.array([5.5, 34.0]), wait=20)
    assert lead.dead > level.dead == 20


def _targets(formation: str, ball_x: float, in_possession: bool, ball_y: float = 34.0):
    m = build_demo_match(3, home_formation=formation)
    pace = {p.player_id: 0.7 for p in m.home.squad + m.away.squad}
    shape = TeamShape.from_sheet(0, m.home.sheet, m.home.tactics, pace)
    other = TeamShape.from_sheet(1, m.away.sheet, m.away.tactics, pace)
    model = MovementModel(np.random.default_rng(0))
    pos = np.zeros((2, 11, 2))
    pos[0], pos[1] = shape.anchors, to_view(other.anchors, 1)
    pos[1, :, 0] = np.maximum(pos[1, :, 0], 5)
    ball = np.array([ball_x, ball_y])
    carrier = (0, 9) if in_possession else (1, 9)
    targets = model.targets(0, (shape, other), pos, ball, 0 if in_possession else 1, carrier, False, (-99, -99), None)
    return dict(zip(range(11), shape.roles)), targets[0]


def test_real_003_wingers_attack_the_box_when_the_ball_is_in_the_final_third():
    roles, deep = _targets("4-3-3", 45.0, True, ball_y=60.0)
    _, high = _targets("4-3-3", 92.0, True, ball_y=60.0)
    rw = next(i for i, r in roles.items() if r == "RW")         # far-side winger: ball on the left
    assert abs(high[rw, 1] - 34) < abs(deep[rw, 1] - 34) - 10
    assert high[rw, 0] > 90


def test_real_003_wide_forwards_drop_into_midfield_without_the_ball():
    roles, t = _targets("4-3-3", 55.0, False)
    lw = next(t[i, 0] for i, r in roles.items() if r == "LW")
    st = next(t[i, 0] for i, r in roles.items() if r == "ST")
    cms = [t[i, 0] for i, r in roles.items() if r == "CM"]          # one of them may be pressing the ball
    assert lw < st - 8
    assert min(abs(lw - x) for x in cms) < 4


def test_real_004_better_finishers_score_more_from_the_same_spot():
    spot = np.array([92.0, 30.0])
    assert xg_model(spot, finishing=0.9) > xg_model(spot, finishing=0.7) > xg_model(spot, finishing=0.5)


def test_real_004_a_much_stronger_side_passes_better_and_makes_more_chances():
    out = Engine(build_demo_match(11, home_strength=60, away_strength=80, home_formation="4-3-3",
                                  away_formation="4-3-3"), 11).run()

    def side(team, key):
        return [e[key] for e in out.events if e["team"] == team and e["type"] in ("pass", "shot") and e.get(key) is not None]
    assert np.mean(side("away", "success_prob")) > np.mean(side("home", "success_prob")) + 0.03
    assert sum(side("away", "xg")) > sum(side("home", "xg"))


# --- chance creation (REAL-005 to REAL-008) -------------------------------------------

@pytest.fixture(scope="module")
def outs():
    return [simulate(build_demo_match(seed)) for seed in (1021, 1022)]


def test_real_005_pass_heights_follow_the_real_mix(outs):
    passes = [e for out in outs for e in out.events if e["type"] == "pass" and e.get("pass_type") != "throw_in"]
    share = {h: sum(e["pass_height"] == h for e in passes) / len(passes) for h in ("ground", "low", "high")}
    assert 0.65 < share["ground"] < 0.85 and 0.04 < share["low"] < 0.14 and 0.1 < share["high"] < 0.25
    long_ = [e for e in passes if e["pass_type"] in ("long_ball", "cross", "corner")]
    assert sum(e["pass_height"] == "high" for e in long_) / len(long_) > 0.6


def test_real_006_keepers_come_for_crosses_and_balls_in_behind(outs):
    actions = [e for out in outs for e in out.events if e["type"] == "goalkeeper"]
    kinds = {e["keeper_action"] for e in actions}
    assert {"claim", "sweep"} <= kinds
    for e in actions:
        if e["keeper_action"] in ("claim", "punch"):
            x = e["location"][0] if e["team"] == "home" else PITCH_LENGTH - e["location"][0]
            assert x <= 13.5                                   # only crosses dropping into his area


def test_real_007_loose_balls_in_front_of_goal_are_struck_first_time(outs):
    for out in outs:
        by_id = {e["event_id"]: e for e in out.events}
        loose = [e for e in out.events if e["type"] == "shot" and e["first_time"]
                 and not any(by_id[r]["type"] == "pass" for r in e.get("related_event_ids", []))]
        assert loose


def test_real_008_long_balls_are_contested_in_the_air(outs):
    aerial = [e for out in outs for e in out.events if e["type"] == "duel" and e["duel_type"] == "aerial"]
    clear = [e for out in outs for e in out.events if e["type"] == "clearance"]
    assert len(aerial) >= 20 and len(clear) >= 30          # was about 10 clearances a match


def test_evt_009_012_cut_out_passes_are_interceptions_or_recoveries(outs):
    for out in outs:
        types = [e["type"] for e in out.events]
        assert types.count("interception") > 5 and types.count("ball_recovery") > types.count("interception")
