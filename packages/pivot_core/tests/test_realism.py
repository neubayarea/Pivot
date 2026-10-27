"""B12 realism rules (docs/sim-realism.md). Test names carry the rule they cover."""

import copy

import numpy as np
import pytest

from pivot_core.domain import MatchEvent
from pivot_core.domain.common import PITCH_LENGTH
from pivot_core.sim import build_demo_match, simulate
from pivot_core.sim.engine import Engine, Params, xg_model
from pivot_core.sim.formations import DEFENDER_ROLES
from pivot_core.sim.movement import BURST_S, RECOVER_MS, SPRINT_MS, MovementModel, TeamShape, to_view


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
    assert min(abs(lw - x) for x in cms) < 6                    # in the midfield line, give or take his drift


def test_real_004_better_finishers_score_more_from_the_same_spot():
    spot = np.array([92.0, 30.0])
    assert xg_model(spot, finishing=0.9) > xg_model(spot, finishing=0.7) > xg_model(spot, finishing=0.5)


def test_real_004_a_much_stronger_side_passes_better_and_makes_more_chances():
    outs = [Engine(build_demo_match(s, home_strength=60, away_strength=80, home_formation="4-3-3",
                                    away_formation="4-3-3"), s).run() for s in (11, 12, 13)]

    def side(team, key):
        return [e[key] for out in outs for e in out.events
                if e["team"] == team and e["type"] in ("pass", "shot") and e.get(key) is not None]
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
    assert len(aerial) >= 20 and len(clear) >= 24          # was about 10 clearances a match


def test_evt_009_012_cut_out_passes_are_interceptions_or_recoveries(outs):
    for out in outs:
        types = [e["type"] for e in out.events]
        assert types.count("interception") > 5 and types.count("ball_recovery") > types.count("interception")


# --- fatigue, injuries, VAR, extra time, referees (REAL-009 to REAL-013) ----------------

def engine_on_ball(seed: int = 21, params: Params | None = None) -> Engine:
    """An engine stopped at a second when somebody has the ball."""
    e = Engine(build_demo_match(seed), seed, params)
    e.play(until_t=300)
    while e.owner is None or e.dead > 0 or e.flight is not None:
        e.play(until_t=e.t + 1)
    return e


def test_real_009_tired_legs_pass_worse():
    e = engine_on_ball()
    fresh, tired = copy.deepcopy(e), copy.deepcopy(e)
    fresh.fitness[:], tired.fitness[:] = 1.0, 0.6
    k, i = e.owner
    for eng in (fresh, tired):
        eng._pass(k, i, eng._view(eng.ball, k), under=False)
    last = [next(x for x in reversed(eng.events) if x["type"] == "pass") for eng in (fresh, tired)]
    assert last[1]["success_prob"] < last[0]["success_prob"]


def test_real_010_a_serious_injury_means_a_substitution_at_the_next_stoppage():
    e = engine_on_ball()
    k = 0
    for i in range(1, 11):                                    # hurt outfield players until one cannot go on
        e._injure(k, i, "contact")
        if e.injured:
            break
    assert e.injured, "no injury worse than a knock in ten tries"
    _, pid = e.injured[0]
    hurt = [x for x in e.events if x["type"] == "injury" and x["player_id"] == pid][-1]
    assert hurt["injury"]["can_continue"] is False and hurt["injury"]["expected_days_out"] > 0
    e.dead = 10
    e._maybe_subs()
    sub = [x for x in e.events if x["type"] == "substitution"][-1]
    assert sub["substitution"]["player_off_id"] == pid and sub["substitution"]["reason"] == "injury"
    assert pid not in e.shapes[k].player_ids


def test_real_010_knocks_are_common_and_players_play_on(outs):
    injuries = [x for out in outs for x in out.events if x["type"] == "injury"]
    assert injuries and sum(x["injury"]["can_continue"] for x in injuries) >= len(injuries) / 2


def test_real_011_var_can_overturn_a_penalty():
    e = engine_on_ball(params=Params(var_pen_overturn=1.0))
    k, i = e.owner
    j = e._nearest(1 - k, e.ball, outfield=True)
    e._foul(1 - k, j, k, i, np.array([100.0, 34.0]))           # a foul in the box
    rev = [x for x in e.events if x["type"] == "var_review"][-1]
    foul = [x for x in e.events if x["type"] == "foul"][-1]
    assert rev["var"]["review_of"] == "penalty" and rev["var"]["decision"] == "overturned"
    assert rev["var"]["reviewed_event_id"] == foul["event_id"] and foul["event_id"] in rev["related_event_ids"]
    assert e.restart["kind"] == "goal_kick" and e.restart["team"] == 1 - k


def test_real_011_var_reviews_point_at_real_events(outs):
    for out in outs:
        ids = {x["event_id"] for x in out.events}
        for rev in (x for x in out.events if x["type"] == "var_review"):
            assert rev["var"]["reviewed_event_id"] in ids


def knockout(seed: int, extra_time: bool = True):
    m = build_demo_match(seed)
    comp = m.context.competition.model_copy(update={"stage": "quarter_final", "extra_time": extra_time,
                                                    "penalty_shootout": True})
    return m.model_copy(update={"context": m.context.model_copy(update={"competition": comp})})


def level_at_80(match) -> Engine:
    e = Engine(match, match.seed)
    e.play(until_t=80 * 60)
    e.score = [1, 1]
    return e


def test_real_012_a_level_knockout_tie_goes_to_extra_time():
    for seed in range(1, 15):
        e = level_at_80(knockout(seed))
        out = e.run()
        if e.score[0] == e.score[1] or out.match.decided_by == "extra_time":
            break
    assert [p.period for p in out.match.periods][:4] == [1, 2, 3, 4]
    assert out.match.decided_by in ("extra_time", "penalties")
    assert np.array_equal(out.frames_t, np.arange(out.frames_t[0], out.frames_t[-1] + 1))   # QA-002 still holds


def test_real_012_a_shootout_decides_a_level_tie():
    for seed in range(1, 15):
        e = level_at_80(knockout(seed, extra_time=False))
        out = e.run()
        if out.match.decided_by == "penalties":
            break
    s = out.match.score
    assert s.home == s.away and s.home_penalties != s.away_penalties
    kicks = [x for x in out.events if x["period"] == 5 and x["type"] == "shot"]
    assert len(kicks) >= 6 and all(x["play_pattern"] == "penalty" and x["shootout_round"] for x in kicks)
    assert sum(x["shot_outcome"] == "goal" for x in kicks if x["team"] == "home") == s.home_penalties
    assert [p.period for p in out.match.periods][-1] == 5
    assert np.array_equal(out.frames_t, np.arange(out.frames_t[0], out.frames_t[-1] + 1))
    out.events_as_models()                                       # every kick follows the data format


def test_real_012_shootout_kicks_go_in_about_three_times_in_four():
    e = engine_on_ball()
    e.record_frames = False
    scored = sum(e._shootout_kick(n % 2, 1 + n % 10, 1 + n // 2) for n in range(400))
    assert 0.7 <= scored / 400 <= 0.85


def test_real_013_a_strict_referee_shows_more_cards():
    cards = {}
    for strict in (30, 90):
        n = 0
        for seed in (31, 32, 33):
            m = build_demo_match(seed)
            ref = m.context.referee.model_copy(update={"strictness": strict, "card_tendency": strict})
            m = m.model_copy(update={"context": m.context.model_copy(update={"referee": ref})})
            e = Engine(m, seed)
            e.record_frames = False
            e.play()
            n += sum(x["type"] == "card" for x in e.events)
        cards[strict] = n
    assert cards[90] > cards[30] * 1.5


# --- running (REAL-014) ------------------------------------------------------------------------

def test_real_014_nobody_reaches_top_speed_in_one_second():
    pos, far = np.zeros((2, 2)), np.full((2, 2), 80.0)
    top, accel = np.array([10.0, 10.0]), np.array([3.0, 5.0])
    _, speed = MovementModel.step(pos, far, top, np.ones(2), np.ones(2, dtype=bool), np.zeros(2), accel)
    assert list(speed) == [3.0, 5.0]                          # the quicker starter gets going faster


def test_real_014_after_a_run_of_sprints_a_player_has_to_jog():
    e = engine_on_ball()
    e.speed[:] = 9.0
    for _ in range(int(BURST_S)):
        e.burst = np.where(e.speed >= SPRINT_MS, e.burst + 1, e.burst)
    e.recovering = e.burst >= BURST_S
    targets = e.pos + np.array([60.0, 0.0])
    e._move(np.clip(targets, 0, [104.5, 67.5]), np.ones((2, 11), dtype=bool))
    assert e.speed.max() <= RECOVER_MS + 1e-9


def test_real_014_wide_players_sprint_more_than_centre_backs(outs):
    counts = {"wide": [], "cb": []}
    for out in outs:
        roles = {s["player_id"]: s["role"] for e in out.events for s in (e.get("team_sheet") or {}).get("starters", [])}
        for k in (0, 1):
            for i in range(11):
                pid = out.frames_ids[0][k][i]
                x = out.frames_speed[:, k, i]
                n = int((np.diff((x >= SPRINT_MS).astype(int)) == 1).sum())
                if roles.get(pid) in ("LW", "RW", "LM", "RM"):
                    counts["wide"].append(n)
                elif roles.get(pid) == "CB":
                    counts["cb"].append(n)
    assert np.mean(counts["wide"]) > np.mean(counts["cb"]) + 10
    assert max(counts["wide"]) < 90                           # a few dozen a match, not a hundred and more


def test_real_011_var_rules_a_goal_out_and_the_score_stays():
    m = build_demo_match(1021)
    e = Engine(m, 1021, Params(var_disallow=1.0))
    e.record_frames = False
    e.play()
    shots = [x for x in e.events if x["type"] == "shot"]
    out = [x for x in shots if x["shot_outcome"] == "disallowed"]
    assert out, "no goal to rule out"
    by_id = {x["event_id"]: x for x in e.events}
    for s in out:
        rev = [by_id[r] for r in s["related_event_ids"] if by_id[r]["type"] == "var_review"]
        assert rev and rev[0]["var"]["review_of"] == "goal" and rev[0]["var"]["decision"] == "overturned"
    goals = [sum(x["shot_outcome"] == "goal" and x["team"] == t for x in shots) for t in ("home", "away")]
    assert goals == e.score                                    # only penalties can still count
    MatchEvent.model_validate({k: v for k, v in out[0].items() if not k.startswith("_") and k != "play_pattern_hint"})


def test_real_016_runners_get_balls_into_space_behind_the_line():
    counts = []
    for lead in (0.0, 1.0):
        e = Engine(build_demo_match(1023), 1023, Params(through_lead=lead))
        e.record_frames = False
        e.play()
        counts.append(sum(x["type"] == "pass" and x.get("pass_type") == "through_ball" for x in e.events))
    assert counts[1] > counts[0] + 10


def _home_targets(press: str, ball_x: float, line_lift: float = 0.0):
    """Home targets out of possession (the away No. 9 on the ball), with the home side pressing `press`."""
    m = build_demo_match(3, home_formation="4-4-2")
    pace = {p.player_id: 0.7 for p in m.home.squad + m.away.squad}
    shape = TeamShape.from_sheet(0, m.home.sheet, m.home.tactics.model_copy(update={"press": press}), pace)
    other = TeamShape.from_sheet(1, m.away.sheet, m.away.tactics, pace)
    model = MovementModel(np.random.default_rng(0))
    model.line_lift = line_lift
    pos = np.zeros((2, 11, 2))
    pos[0], pos[1] = shape.anchors, to_view(other.anchors, 1)
    ball = np.array([ball_x, 34.0])
    targets = model.targets(0, (shape, other), pos, ball, 1, (1, 9), False, (-99, -99), None)
    return shape.roles, targets[0], model.pressers


def test_real_015_every_back_line_sits_line_lift_metres_higher():
    lift = Params().line_lift
    assert lift > 0
    roles, flat, _ = _home_targets("low", 52.5)
    _, lifted, _ = _home_targets("low", 52.5, line_lift=lift)
    backs = [i for i, r in enumerate(roles) if r in DEFENDER_ROLES]
    assert np.allclose(lifted[backs, 0] - flat[backs, 0], lift)


def test_real_015_low_and_mid_blocks_only_press_near_their_own_goal():
    # PRESS_ZONE: a low block closes down inside 40 m of its goal, a mid block inside 60 m, a high one everywhere
    pressing = {p: {b: bool(_home_targets(p, b)[2]) for b in (35.0, 50.0, 70.0)} for p in ("low", "mid", "high")}
    assert pressing["low"] == {35.0: True, 50.0: False, 70.0: False}
    assert pressing["mid"] == {35.0: True, 50.0: True, 70.0: False}
    assert pressing["high"] == {35.0: True, 50.0: True, 70.0: True}


def _cross_targets(ball_y: float):
    """Home targets with the near-side winger on the ball 17 m from goal and the away side back on its line."""
    m = build_demo_match(3, home_formation="4-3-3")
    pace = {p.player_id: 0.7 for p in m.home.squad + m.away.squad}
    shape = TeamShape.from_sheet(0, m.home.sheet, m.home.tactics, pace)
    other = TeamShape.from_sheet(1, m.away.sheet, m.away.tactics, pace)
    model = MovementModel(np.random.default_rng(0))
    pos = np.zeros((2, 11, 2))
    pos[0], pos[1] = shape.anchors, to_view(other.anchors, 1)
    pos[1, :, 0] = 101.0                                            # nobody to be offside against short of the line
    ball = np.array([88.0, ball_y])
    near = next(i for i, r in enumerate(shape.roles) if r == "LW")  # ball on the left: the left winger has it
    targets = model.targets(0, (shape, other), pos, ball, 0, (0, near), False, (-99, -99), None)
    return shape.roles, targets[0]


def test_real_017_forwards_attack_the_six_yard_box_when_a_cross_is_coming():
    roles, central = _cross_targets(34.0 + 12)
    _, wide = _cross_targets(34.0 + 25)                             # out by the touchline: a cross is coming
    st, far = roles.index("ST"), roles.index("RW")                  # the right winger is on the far side
    assert wide[st, 0] > central[st, 0] + 3 and wide[st, 0] > PITCH_LENGTH - 7
    assert wide[far, 0] > central[far, 0] + 3


def _shoots(close_in: float, tries: int = 2000) -> int:
    """How often a free striker at a tight angle in the box shoots, every other choice stubbed out."""
    e = engine_on_ball(params=Params(close_in=close_in))
    k, i = 0, next(n for n, r in enumerate(e.shapes[0].roles) if r == "ST")
    v = np.array([90.0, 27.0])                    # in the box, so the long-shot rule stays out of it
    e.owner, e.forced, e.touch, e.urgency = (k, i), None, None, [0.0, 0.0]
    e.pos[k, i], e.ball = v, v.copy()
    e.pos[1], e.prev[1] = np.array([20.0, 34.0]), np.array([20.0, 34.0])   # nobody near him
    shots = []
    e._shoot = lambda *a, **kw: shots.append(1)
    e._pass = e._carry = e._dribble = e._challenge = e._clearance = lambda *a, **kw: None
    xg = xg_model(v, finishing=e._a(k, i, "finishing"))
    assert e.p.shot_min_xg <= xg < 0.15                             # worth a shot, but he can still make it better
    for _ in range(tries):
        e._on_ball()
    return len(shots)


def test_real_017_a_free_player_takes_a_poor_chance_closer_before_shooting():
    rule_on, rule_off = _shoots(Params().close_in), _shoots(1.0)
    assert Params().close_in < 1
    assert rule_off > 100 and rule_on < 0.7 * rule_off


def test_347_a_keeper_sent_off_is_replaced_in_goal_and_goal_kicks_still_have_a_taker():
    e = engine_on_ball()
    k = 0
    gk = e._keeper(k)
    assert gk is not None
    keeper_id = e.shapes[k].player_ids[gk]
    e.shapes[k].player_ids[gk] = None                        # sent off, as _foul does on a red card
    e._react_to_red(k)
    new = e._keeper(k)
    assert new is not None and e.shapes[k].player_ids[new] not in (None, keeper_id)
    taker = e._choose_taker(k, "goal_kick", e.ball.copy())
    assert taker == new and e.shapes[k].player_ids[taker] is not None
