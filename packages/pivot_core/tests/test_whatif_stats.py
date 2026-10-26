"""Bx10: each What-if run also says what the teams did after the change, not just who won."""

import hashlib

import pytest

from pivot_core.domain import OutcomeDist, ScenarioSpec, SimResult, TeamTactics
from pivot_core.sim import DEMO_1021
from pivot_core.sim.whatif import (
    RUN_STATS, Run, _score, copy_engine, describe, play_counted, play_on, prepare, run_whatif, save, spread,
    summarise,
)

PLANTS = list(DEMO_1021.plants)
SEEDS = range(1000, 1006)


def spec(type_, at_minute, **kw):
    return ScenarioSpec(type=type_, pivot_id="p1", at_minute=at_minute, seed_base=1000, **kw)


@pytest.fixture(scope="module")
def starts():
    """Both arms of a press change at 85', so each run is only a few minutes of play."""
    return prepare(save(DEMO_1021.build(), 85, plants=PLANTS),
                   spec("change_press", 85, team="home", tactics=TeamTactics(press="high")))


def hand_count(start, seed):
    """The same numbers, counted from a plain run with frames switched on."""
    eng = copy_engine(start)
    eng.record_frames = True
    first, before = len(eng.events), list(eng.score)
    eng = play_on(eng, seed)
    side = []
    for k, team in enumerate(("home", "away")):
        evs = [e for e in eng.events[first:] if e["team"] == team and e["period"] != 5]
        shots = [e for e in evs if e["type"] == "shot"]
        cards = [e for e in evs if e["type"] == "card"]
        side.append((eng.score[k] - before[k], len(shots), sum(e["shot_outcome"] in ("goal", "saved") for e in shots),
                     round(sum(e["xg"] for e in shots), 4), sum(p == k for p in eng.frames["poss"]), len(cards),
                     sum(e["foul"]["card"] in ("red", "second_yellow") for e in cards)))
    return Run(_score(eng), *side)


def test_bx10_counted_runs_play_the_same_match(starts):
    for start in starts:
        old = [_score(play_on(start, s)) for s in SEEDS]
        new = [play_counted(start, s) for s in SEEDS]
        assert [r.score for r in new] == old
        assert summarise([r.score for r in new]).model_dump_json() == summarise(old).model_dump_json()


def test_bx10_counted_numbers_match_a_hand_count(starts):
    for start in starts:
        for s in SEEDS:
            got, want = play_counted(start, s), hand_count(start, s)
            assert got.score == want.score
            for k in (1, 2):
                assert got[k][:4] == want[k][:4] and got[k][5:] == want[k][5:]
                assert abs(got[k][4] - want[k][4]) <= 2          # possession seconds, read a step later


def test_bx10_describe_matches_a_hand_count():
    #       goals shots on xg   poss cards reds
    runs = [Run((2, 1), (1, 4, 2, 0.8, 30, 0, 0), (0, 2, 1, 0.3, 10, 1, 0)),
            Run((1, 1), (0, 1, 0, 0.1, 20, 1, 0), (1, 3, 2, 0.6, 20, 0, 0)),
            Run((2, 1), (1, 3, 1, 0.5, 15, 0, 0), (0, 0, 0, 0.0, 45, 2, 1)),
            Run((1, 2), (0, 0, 0, 0.0, 0, 0, 0), (1, 5, 3, 1.2, 0, 0, 0))]
    a = describe(runs, from_t=2220)
    assert a.n_runs == 4 and a.from_t == 2220
    assert [(s.home, s.away, s.share) for s in a.top_scores] == [(2, 1, 0.5), (1, 1, 0.25), (1, 2, 0.25)]
    assert a.home.goals.mean == 0.5 and a.home.goals.sd == 0.5 and a.home.scored_share == 0.5
    assert a.away.scored_share == 0.5
    assert a.home.shots.mean == 2.0 and (a.home.shots.p10, a.home.shots.p90) == (0, 4)
    assert a.away.xg.mean == 0.525
    assert a.away.red_cards.mean == 0.25 and a.away.cards.mean == 0.75
    # possession: 75 %, 50 %, 25 %, and 50 % when nobody had the ball
    assert a.home.possession_pct.mean == 50.0 and a.away.possession_pct.mean == 50.0
    assert a.home.possession_pct.sd == pytest.approx(17.678, abs=1e-3)
    assert spread([3, 1, 2]).model_dump() == {"mean": 2.0, "sd": 0.816, "p10": 1, "p90": 3}
    assert len(RUN_STATS) == len(runs[0].home)


def test_bx10_an_old_result_without_stats_still_loads():
    dist = OutcomeDist(home_win=0.5, draw=0.3, away_win=0.2, ci95={"home_win": (0.4, 0.6)})
    old = {"scenario_id": "demo:s1", "baseline": dist.model_dump(), "counterfactual": dist.model_dump(),
           "significant": {"home_win": False}, "narrative": None, "runtime_ms": 10, "executor": "local_pool"}
    res = SimResult.model_validate(old)
    assert res.baseline_stats is None and res.counterfactual_stats is None
    assert SimResult.model_validate_json(res.model_dump_json()) == res
    schema = SimResult.model_json_schema(mode="serialization")
    assert "baseline_stats" not in schema["required"] and "baseline" in schema["required"]


def test_bx10_same_numbers_on_every_platform():
    """Pinned on Windows; the Mac CI runner must get the same (#192). A change to the counting
    or the run of play shows up here: rerun and update the pin, saying so in the PR."""
    res = run_whatif(DEMO_1021.build(), spec("change_press", 85, team="home", tactics=TeamTactics(press="high")),
                     plants=PLANTS, workers=1, n_runs=6)
    numbers = res.model_dump_json(include={"baseline", "counterfactual", "baseline_stats", "counterfactual_stats"})
    assert hashlib.sha256(numbers.encode()).hexdigest()[:16] == PIN, numbers


PIN = "efcb51c2c32fd459"
