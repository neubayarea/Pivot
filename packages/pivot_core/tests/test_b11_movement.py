"""B11 acceptance: the movement model puts the 22 players in their formation (tasks.csv, issue #55).

Each condition is checked twice where it can be: once on the movement model alone, with
everything else held still, and once over a few simulated matches, where the run of play
also changes. The low-versus-high line check sits in test_sim.py.
"""

from functools import cache

import numpy as np
import pytest

from pivot_core.domain import PlayerInstruction
from pivot_core.sim import build_demo_match, simulate
from pivot_core.sim.formations import DEFENDER_ROLES, MIDFIELD_ROLES
from pivot_core.sim.movement import SPRINT_MS, MovementModel, TeamShape, to_view

SEEDS = (1, 2)


def with_tactics(m, **update):
    tactics = m.home.tactics.model_copy(update=update)
    return m.model_copy(update={"home": m.home.model_copy(update={"tactics": tactics})})


def shapes(m):
    return tuple(TeamShape.from_sheet(k, team.sheet, team.tactics, {p.player_id: 0.7 for p in team.squad})
                 for k, team in enumerate((m.home, m.away)))


def start_positions(home: TeamShape, away: TeamShape) -> np.ndarray:
    pos = np.zeros((2, 11, 2))
    pos[0] = home.anchors
    pos[1] = to_view(away.anchors, 1)
    return pos


def defending_targets(m, ball_x: float) -> tuple[TeamShape, np.ndarray, set[int]]:
    """Home targets while the away striker holds the ball `ball_x` metres from the home goal,
    and the home slots sent to close the ball down."""
    home, away = shapes(m)
    pos = start_positions(home, away)
    ball = np.array([ball_x, 34.0])
    model = MovementModel(np.random.default_rng(0))
    targets = model.targets(0, (home, away), pos, ball, 1, (1, 9), False, (-99, -99), None)
    return home, targets[0], {i for k, i in model.pressers if k == 0}


def attacking_targets(m) -> tuple[TeamShape, np.ndarray]:
    """Home targets while the home central midfielder has the ball just inside the other half."""
    home, away = shapes(m)
    pos = start_positions(home, away)
    targets = MovementModel(np.random.default_rng(0)).targets(0, (home, away), pos, np.array([60.0, 34.0]), 0,
                                                               (0, 6), False, (-99, -99), None)
    return home, targets[0]


def mean_x(shape: TeamShape, xy: np.ndarray, roles, skip=()) -> float:
    return float(np.mean([xy[i, 0] for i, r in enumerate(shape.roles) if r in roles and i not in skip]))


OUTFIELD = DEFENDER_ROLES | MIDFIELD_ROLES | {"LW", "RW", "ST"}


@cache
def sim(seed: int, formation: str = "4-4-2", press: str = "mid"):
    m = with_tactics(build_demo_match(seed, home_formation=formation), press=press)
    return m, simulate(m)


def defending_seconds(out):
    """(frame, away carrier position) for every second an away player has the ball at their feet."""
    for n, owner in enumerate(out.frames_owner):
        ids = out.frames_ids[n][1]
        if out.frames_possession[n] == 1 and owner is not None and owner in ids:
            yield n, out.frames_pos[n, 1, ids.index(owner)]


def home_back_line_when_defending(m, out) -> float:
    roles = {s.player_id: s.role for s in m.home.sheet.starters}
    xs = []
    for n, _ in defending_seconds(out):
        line = [out.frames_pos[n, 0, i, 0] for i, p in enumerate(out.frames_ids[n][0])
                if p and roles.get(p) in DEFENDER_ROLES]
        if line:
            xs.append(np.mean(line))
    return float(np.mean(xs))


def nearest_home_player_to_carrier(out) -> float:
    d = []
    for n, carrier in defending_seconds(out):
        on = [i for i, p in enumerate(out.frames_ids[n][0]) if p]
        d.append(np.hypot(*(out.frames_pos[n, 0, on] - carrier).T).min())
    return float(np.mean(d))


# --- 5-4-1 drops the back line ---------------------------------------------------------------

@pytest.mark.parametrize("ball_x", [30.0, 50.0, 70.0])
def test_b11_five_four_one_drops_the_back_line(ball_x):
    # the one or two players sent to close the ball down are not part of the line
    four, t4, press4 = defending_targets(build_demo_match(3, home_formation="4-4-2"), ball_x)
    five, t5, press5 = defending_targets(build_demo_match(3, home_formation="5-4-1"), ball_x)
    assert mean_x(five, t5, DEFENDER_ROLES, press5) < mean_x(four, t4, DEFENDER_ROLES, press4) - 1.5
    # the whole block sits deeper, not only the defenders
    assert mean_x(five, t5, OUTFIELD, press5) < mean_x(four, t4, OUTFIELD, press4) - 4


def test_b11_five_four_one_drops_the_back_line_over_whole_matches():
    # about 2 m deeper on these seeds (1.0 and 2.9); the run of play adds noise on top of the shape
    four = np.mean([home_back_line_when_defending(*sim(s, "4-4-2")) for s in SEEDS])
    five = np.mean([home_back_line_when_defending(*sim(s, "5-4-1")) for s in SEEDS])
    assert five < four - 1.0


# --- a higher press closes the ball carrier down -----------------------------------------------

def mean_distance_to_carrier(press: str, ball_x: float, seconds: int = 40) -> float:
    """Let the home side move for `seconds` while the away striker holds the ball still."""
    m = with_tactics(build_demo_match(3, home_formation="4-4-2"), press=press)
    home, away = shapes(m)
    pos = start_positions(home, away)
    ball = np.array([ball_x, 34.0])
    pos[1, 9] = ball
    model = MovementModel(np.random.default_rng(0))
    d = []
    for t in range(seconds):
        targets = model.targets(t, (home, away), pos, ball, 1, (1, 9), False, (-99, -99), None)
        pos[0], _ = MovementModel.step(pos[0], targets[0], home.pace, np.ones(11), home.active)
        if t >= 10:
            outfield = [i for i, r in enumerate(home.roles) if r != "GK"]
            d.append(np.hypot(*(pos[0, outfield] - ball).T).mean())
    return float(np.mean(d))


def test_b11_higher_press_stands_closer_to_the_ball_carrier():
    low, mid, high = (mean_distance_to_carrier(p, ball_x=60.0) for p in ("low", "mid", "high"))
    assert high < mid < low


def test_b11_higher_press_stands_closer_to_the_ball_carrier_over_whole_matches():
    # low to mid, which reuses the matches above; mid to high is a few centimetres in a whole match
    low = np.mean([nearest_home_player_to_carrier(sim(s, press="low")[1]) for s in SEEDS])
    mid = np.mean([nearest_home_player_to_carrier(sim(s)[1]) for s in SEEDS])
    assert mid < low - 0.3


# --- an overlapping full back gets further forward ---------------------------------------------

def test_b11_overlapping_full_back_stands_further_forward_in_attack():
    m = build_demo_match(3, home_formation="4-4-2")
    lb = next(s for s in m.home.sheet.starters if s.role == "LB")
    plain, before = attacking_targets(m)
    told = with_tactics(m, instructions=[PlayerInstruction(player_id=lb.player_id, instruction="overlap")])
    _, after = attacking_targets(told)
    i = lb.slot - 1
    assert after[i, 0] > before[i, 0] + 8
    others = [j for j in range(11) if j != i]
    assert np.allclose(after[others], before[others])   # nobody else is told to move


# --- top speed 8.5 m/s, slower when tired ------------------------------------------------------

def test_b11_top_speed_is_8_5_and_falls_with_fitness():
    pos = np.zeros((3, 2))
    far = np.full((3, 2), 60.0)
    pace = np.ones(3)                                  # the fastest possible player
    _, speed = MovementModel.step(pos, far, pace, np.array([1.0, 0.7, 0.4]), np.ones(3, dtype=bool))
    assert speed[0] == pytest.approx(SPRINT_MS)
    assert SPRINT_MS == 8.5
    assert speed[0] > speed[1] > speed[2]


@pytest.mark.xfail(strict=True, reason="the engine moves a throw-in receiver up to 22 m in one second (and a "
                   "player in a corner duel 9 m); handed to B12, which owns engine.py")
def test_b11_nobody_moves_faster_than_8_5_between_two_frames():
    for s in SEEDS:
        out = sim(s)[1]
        step = np.hypot(*np.diff(out.frames_pos, axis=0).transpose(3, 0, 1, 2))
        same_period = out.frames_period[1:] == out.frames_period[:-1]
        same_player = np.array([[[a == b and a is not None for a, b in zip(x[k], y[k])] for k in (0, 1)]
                                for x, y in zip(out.frames_ids, out.frames_ids[1:])])
        assert step[same_period[:, None, None] & same_player].max() <= SPRINT_MS + 0.01


def test_b11_top_speed_holds_and_tired_players_are_slower_over_whole_matches():
    speed = np.concatenate([sim(s)[1].frames_speed.ravel() for s in SEEDS])
    fitness = np.concatenate([sim(s)[1].frames_fitness.ravel() for s in SEEDS])
    assert speed.max() <= SPRINT_MS
    fresh = speed[(fitness >= 0.9) & (speed > 0)]
    tired = speed[(fitness < 0.8) & (speed > 0)]
    assert len(tired) > 1000
    assert np.percentile(tired, 99) < np.percentile(fresh, 99) - 0.2
