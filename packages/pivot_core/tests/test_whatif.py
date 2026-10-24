"""What-if checks: save and play on (B04), scenarios and the batch of reruns (B08)."""

import pytest

from pivot_core.domain import ScenarioSpec, TeamTactics
from pivot_core.sim import DEMO_1021, simulate
from pivot_core.sim.whatif import (
    copy_engine, play_on, prepare, run_arms, run_whatif, save, significant, summarise, wilson,
)

PLANTS = list(DEMO_1021.plants)


def strip(events):
    return [{k: v for k, v in e.items() if not k.startswith("_")} for e in events]


def played(eng, minutes, seed=5):
    """A reseeded copy of `eng` played on for a few minutes."""
    c = copy_engine(eng)
    c.reseed(seed)
    c.play(until_t=c.t + minutes * 60)
    return c


def later(eng, since_t, type_):
    return [e for e in eng.events if e["t"] >= since_t and e["type"] == type_]


@pytest.fixture(scope="module")
def ref():
    """The demo match as it was played (raw events, so planted ones carry their plant)."""
    return simulate(DEMO_1021.build(), plants=PLANTS)


@pytest.fixture(scope="module")
def saved37():
    return save(DEMO_1021.build(), 37, plants=PLANTS)


def save_at(saved, minute):
    """The same match saved later: with the original seed a copy plays on as the real match did."""
    s = copy_engine(saved)
    s.play(until_t=minute * 60)
    return s


@pytest.fixture(scope="module")
def saved56(saved37):
    return save_at(saved37, 56)


@pytest.fixture(scope="module")
def saved64(saved56):
    return save_at(saved56, 64)


def spec(type_, at_minute, **kw):
    return ScenarioSpec(type=type_, pivot_id="p1", at_minute=at_minute, seed_base=1000, **kw)


def event_id(ref, pred):
    return next(e["event_id"] for e in ref.events if pred(e))


def is_red(e):
    return e["type"] == "card" and e["foul"]["card"] == "red"


def is_planted_sub(e):
    return e["type"] == "substitution" and e["substitution"]["reason"] == "tactical"


def subs(eng, since_t):
    return [(e["substitution"]["player_off_id"], e["substitution"]["player_on_id"])
            for e in later(eng, since_t, "substitution")]


# --- B04: save and play on -------------------------------------------------------------

def test_b04_playing_on_from_a_save_gives_the_same_match(ref, saved37):
    assert saved37.t == 37 * 60
    for _ in range(2):                                   # the save itself is not used up
        out = play_on(saved37)
        out._finalise()
        assert strip(out.events) == strip(ref.events)
        assert out.score == [ref.match.score.home, ref.match.score.away]
    assert saved37.t == 37 * 60


def test_b04_reseeded_runs_share_the_history_and_then_differ(ref, saved37):
    a, b = played(saved37, 5, seed=1), played(saved37, 5, seed=2)
    n = len(saved37.events)
    assert strip(a.events[:n]) == strip(b.events[:n]) == strip(saved37.events)
    assert strip(a.events[n:]) != strip(b.events[n:])
    assert strip(played(saved37, 5, seed=1).events) == strip(a.events)     # same seed, same rerun


# --- B08: scenarios --------------------------------------------------------------------

def test_b08_remove_red_card_keeps_the_player_on(ref, saved37):
    red = next(e for e in ref.events if is_red(e))
    base, cf = prepare(saved37, spec("remove_red_card", 37, target_event_id=red["event_id"], team="away"))
    b, c = played(base, 4), played(cf, 4)
    assert [e["player_id"] for e in b.events if is_red(e) and e["t"] >= 37 * 60] == [red["player_id"]]
    assert not [e for e in c.events if is_red(e) and e["t"] >= 37 * 60]
    assert sum(p is not None for p in c.shapes[1].player_ids) == 11
    assert sum(p is not None for p in b.shapes[1].player_ids) == 10


def test_b08_cancel_a_natural_substitution_keeps_both_players(ref, saved56):
    sub = event_id(ref, lambda e: e["type"] == "substitution" and e["team"] == "home")
    assert sub.startswith("m058")                         # h08 off for h16, a fatigue change
    s = save_at(saved56, 58)
    base, cf = prepare(s, spec("cancel_substitution", 58, target_event_id=sub, team="home"))
    assert ("h08", "h16") in subs(played(base, 3), 58 * 60)          # forced back into the baseline
    after = played(cf, 25)
    assert not [p for p in subs(after, 58 * 60) if {"h08", "h16"} & set(p)]
    assert "h08" in after.shapes[0].player_ids


def test_b08_cancel_the_planted_63_change_cancels_its_tactics_too(ref, saved64):
    sub = event_id(ref, is_planted_sub)
    base, cf = prepare(saved64, spec("cancel_substitution", 64, target_event_id=sub, team="home"))
    b, c = played(base, 4), played(cf, 4)
    assert ("h09", "h15") in subs(b, 64 * 60) and b.tactics[0].line_height == "low"
    assert ("h09", "h15") not in subs(c, 64 * 60) and c.tactics[0].line_height == "mid"


def test_b08_move_the_planted_substitution_to_75(ref, saved64):
    sub = event_id(ref, is_planted_sub)
    base, cf = prepare(saved64, spec("move_substitution", 64, target_event_id=sub, team="home",
                                     params={"new_minute": 74}))
    c = played(cf, 8)
    assert ("h09", "h15") not in subs(c, 64 * 60) and c.tactics[0].line_height == "mid"
    c.play(until_t=82 * 60)
    moved = [e for e in later(c, 64 * 60, "substitution") if e["substitution"]["player_off_id"] == "h09"]
    assert moved and moved[0]["period_t"] >= (74 - 45) * 60                 # 75' on the clock or later
    assert c.tactics[0].line_height == "low"


def test_b08_keep_press_and_line_at_63_still_makes_the_substitution(ref, saved64):
    sub = event_id(ref, is_planted_sub)
    before = TeamTactics(line_height="mid", press="mid")
    _, cf = prepare(saved64, spec("change_tactics", 64, target_event_id=sub, team="home", tactics=before))
    c = played(cf, 4)
    assert ("h09", "h15") in subs(c, 64 * 60)
    assert (c.tactics[0].line_height, c.tactics[0].press) == ("mid", "mid")


def test_b08_change_press_only_overrides_the_press(saved64):
    _, cf = prepare(saved64, spec("change_press", 64, team="home", tactics=TeamTactics(press="high")))
    c = played(cf, 4)
    assert (c.tactics[0].line_height, c.tactics[0].press) == ("low", "high")


def test_b08_change_formation_and_lineup(saved64):
    sheet = saved64.sheets[1].model_copy(update={"formation": "5-4-1"})
    _, cf = prepare(saved64, spec("change_formation", 64, team="away", team_sheet=sheet))
    assert cf.sheets[1].formation == "5-4-1"
    assert sum(p is not None for p in cf.shapes[1].player_ids) == 10

    home = saved64.sheets[0]
    off = next(s for s in home.starters if s.role != "GK" and s.player_id in saved64.shapes[0].player_ids)
    on = next(b for b in home.bench if saved64.players[b].role != "GK")
    starters = [s.model_copy(update={"player_id": on}) if s is off else s for s in home.starters]
    _, cf = prepare(saved64, spec("change_lineup", 64, team="home",
                                  team_sheet=home.model_copy(update={"starters": starters})))
    assert (off.player_id, on) in subs(played(cf, 4), 64 * 60)


def test_b08_remove_goal_takes_it_off_the_score(ref, saved37):
    goal = next(e for e in ref.events if e["type"] == "shot" and e["shot_outcome"] == "goal" and e["t"] >= 37 * 60)
    k = 0 if goal["team"] == "home" else 1
    base, cf = prepare(saved37, spec("remove_goal", goal["t"] // 60 + 1, target_event_id=goal["event_id"],
                                     team=goal["team"]))
    assert base.score[k] == cf.score[k] + 1 and base.score[1 - k] == cf.score[1 - k]
    assert base.t == cf.t and cf.restart["kind"] == "goal_kick" and cf.restart["team"] == 1 - k


def test_b08_scenarios_reject_a_wrong_target(ref, saved37, saved64):
    sub = event_id(ref, is_planted_sub)
    with pytest.raises(ValueError):
        prepare(saved64, spec("remove_red_card", 64, target_event_id=sub))            # not a red card
    with pytest.raises(ValueError):
        prepare(saved64, spec("remove_red_card", 64, target_event_id=event_id(ref, is_red)))   # already past
    with pytest.raises(ValueError):
        prepare(saved64, spec("remove_red_card", 64, target_event_id="m999-s99999"))


# --- B08: batch and statistics ---------------------------------------------------------

def test_b08_wilson_interval():
    lo, hi = wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-4) and hi == pytest.approx(0.7634, abs=1e-4)
    assert wilson(0, 10) == (0.0, pytest.approx(0.2775, abs=1e-4))
    a = summarise([(1, 0)] * 90 + [(0, 0)] * 10)
    b = summarise([(1, 0)] * 40 + [(0, 0)] * 60)
    assert a.home_win == 0.9 and a.away_win == 0.0
    assert significant(a, b) == {"home_win": True, "draw": True, "away_win": False}
    assert not any(significant(a, a).values())


def test_b08_paired_runs_do_not_depend_on_the_pool(ref, saved64):
    late = save_at(saved64, 88)
    starts = list(prepare(late, spec("change_press", 88, team="home", tactics=TeamTactics(press="high"))))
    calls = []
    alone = run_arms(starts, 4, 1000, workers=1)
    pooled = run_arms(starts, 4, 1000, workers=2, progress=lambda d, t: calls.append((d, t)))
    assert alone == pooled
    assert calls[-1] == (8, 8)
    assert all(h >= 1 for arm in alone for h, _ in arm)                    # Harbour City were 1-0 up at 88'


def test_b08_run_whatif_returns_a_sim_result():
    m = DEMO_1021.build()
    sp = spec("change_press", 89, team="home", tactics=TeamTactics(press="high"))
    res = run_whatif(m, sp, plants=PLANTS, workers=1, n_runs=3, scenario_id="demo:s1")
    assert res.executor == "local_pool" and res.scenario_id == "demo:s1" and res.runtime_ms > 0
    for dist in (res.baseline, res.counterfactual):
        assert dist.home_win + dist.draw + dist.away_win == pytest.approx(1)
        assert set(dist.ci95) == {"home_win", "draw", "away_win"}
    assert set(res.significant) == {"home_win", "draw", "away_win"}
