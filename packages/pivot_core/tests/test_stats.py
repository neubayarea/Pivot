"""StatCalculator (B05). Each test is named after the data definition it checks (MET-xxx, RAT-xxx).

Most tests use a tiny hand-made match whose right answer can be read off the events; the last
ones run on a simulated match and check that the numbers hang together.
"""

import typing

import pytest

from pivot_core.analytics import StatCalculator, player_match_stats
from pivot_core.analytics.ratings import POSITION_OFFSET
from pivot_core.domain import (
    ExplanationSentence,
    MatchEvent,
    Narrative,
    StatMetric,
    StatRef,
    TrackingFrame,
    ViewerPrefs,
)
from pivot_core.domain.stats import Claim
from pivot_core.sim import build_demo_match, simulate

MATCH = build_demo_match(5)
MID = MATCH.match_id


def ev(seq: int, t: int, type_: str, team: str = "home", **kw) -> MatchEvent:
    period = 1 if t < 2700 else 2
    return MatchEvent(match_id=MID, seq=seq, event_id=f"e{seq}", t=t, period=period,
                      period_t=t if period == 1 else t - 2700, type=type_, team=team, **kw)


def frame(t: int, possession, players: dict, owner=None) -> TrackingFrame:
    return TrackingFrame(match_id=MID, t=t, period=1 if t < 2700 else 2, possession=possession,
                         ball={"x": 52.5, "y": 34.0, "owner_id": owner},
                         players=[{"player_id": k, "x": v[0], "y": v[1]} for k, v in players.items()])


def calc(events=(), frames=()) -> StatCalculator:
    return StatCalculator(MATCH, list(events), list(frames))


def ask(c: StatCalculator, metric: str, team: str = "home", window=(0, 120), player=None) -> float:
    return c.compute(StatRef(metric=metric, team=team, window=window, player_id=player))


def test_every_metric_in_the_vocabulary_is_implemented():
    c = calc([ev(1, 10, "pass", location=(30, 30), end_location=(40, 30), outcome="success")])
    for metric in typing.get_args(StatMetric):
        try:
            value = ask(c, metric)
        except LookupError:                        # no frames, nothing to divide by: "no data", never a number
            continue
        assert isinstance(value, float) and value == value


# --- no data is "no data", not NaN or 0 ---------------------------------------------

NO_FRAMES = ("possession_pct", "line_height_m", "team_width_m", "press_distance_m", "distance_covered_km")


@pytest.mark.parametrize("metric", ["pass_accuracy_pct", "ppda", "field_tilt_pct", "momentum_avg", *NO_FRAMES])
def test_a_window_with_nothing_to_measure_has_no_value(metric):
    c = calc([ev(1, 10, "pass", location=(30, 30), end_location=(40, 30), outcome="success")])
    with pytest.raises(LookupError):
        ask(c, metric, window=(50, 55))


@pytest.mark.parametrize("metric", NO_FRAMES)
def test_frame_metrics_without_frames_have_no_value(metric):
    with pytest.raises(LookupError):
        ask(calc([ev(1, 10, "pass", outcome="success")]), metric)


@pytest.mark.parametrize("metric", ["possession_pct", "team_width_m", "ppda", "field_tilt_pct", "momentum_avg"])
def test_team_only_metrics_have_no_value_for_a_player(metric):
    with pytest.raises(LookupError, match="team"):
        ask(calc(), metric, player="h09")


def test_an_unknown_player_or_one_from_the_other_side_has_no_value():
    c = calc([ev(1, 10, "pass", player_id="h09", outcome="success")])
    assert ask(c, "passes", player="h09") == 1
    with pytest.raises(LookupError, match="no player"):
        ask(c, "passes", player="x99")
    with pytest.raises(LookupError, match="away"):
        ask(c, "passes", player="a09")                  # asked about home, a09 plays for away


def test_a_missing_match_has_no_values():
    c = StatCalculator(None, [], [])                     # what load_view passes for a match it cannot find
    with pytest.raises(LookupError, match="match"):
        ask(c, "shots")


def test_the_real_verifier_rejects_any_number_for_a_window_without_data():
    verifier = pytest.importorskip("pivot_worker.verifier")
    es = [ev(i, 61 * 60 + i, "pass", outcome="success" if i % 4 else "fail") for i in range(1, 9)]
    c = calc(es)
    assert ask(c, "pass_accuracy_pct", window=(61, 66)) == 75.0

    def check(value, window):
        ref = StatRef(metric="pass_accuracy_pct", team="home", window=window)
        sentence = ExplanationSentence(text=f"Pass accuracy was {value:g}%.", evidence_ids=["e1"],
                                       claims=[Claim(value=value, unit="pct", stat_ref=ref)])
        card = Narrative(prefs=ViewerPrefs(), headline="Passing goes up a gear", sentences=[sentence], source="llm")
        return verifier.verify(card, pivot_minute=63, events={e.event_id: e for e in es}, stats=c)

    assert check(75.0, (61, 66)).passed
    for wrong in (87.0, 12.0):                         # nothing happened in 40-45: no percentage can be right
        verdict = check(wrong, (40, 45))
        assert not verdict.passed
        assert any("cannot be recomputed" in i.message for i in verdict.issues), verdict.issues


def test_window_is_left_closed_right_open_on_elapsed_minutes():
    c = calc([ev(1, 62 * 60 + 59, "shot", xg=0.1), ev(2, 63 * 60, "shot", xg=0.1), ev(3, 68 * 60, "shot", xg=0.1)])
    assert ask(c, "shots", window=(63, 68)) == 1


def test_shootout_never_counts():
    shootout = MatchEvent(match_id=MID, seq=9, event_id="p1", t=7400, period=5, period_t=10, type="shot",
                          team="home", xg=0.76, shot_outcome="goal", play_pattern="penalty", shootout_round=1)
    assert ask(calc([shootout]), "shots") == 0


def test_met_001_possession_counts_live_frames_only():
    fs = [frame(0, "home", {}), frame(1, "home", {}), frame(2, "away", {}), frame(3, None, {})]
    assert ask(calc(frames=fs), "possession_pct") == pytest.approx(66.7)
    with pytest.raises(LookupError):
        ask(calc(frames=fs), "possession_pct", player="h09")


def test_met_002_003_passes_and_accuracy_leave_out_throw_ins():
    es = [ev(1, 10, "pass", outcome="success"), ev(2, 11, "pass", outcome="fail"),
          ev(3, 12, "pass", outcome="success", pass_type="throw_in")]
    c = calc(es)
    assert ask(c, "passes") == 2
    assert ask(c, "pass_accuracy_pct") == 50.0


def test_met_004_final_third_counts_successful_passes_ending_there():
    es = [ev(1, 10, "pass", outcome="success", location=(60, 30), end_location=(75, 30)),
          ev(2, 11, "pass", outcome="fail", location=(60, 30), end_location=(80, 30)),
          ev(3, 12, "pass", outcome="success", location=(45, 30), end_location=(30, 30), team="away")]
    c = calc(es)
    assert ask(c, "passes_final_third") == 1
    assert ask(c, "passes_final_third", team="away") == 1          # away attacks towards x = 0


def test_met_005_box_entries_need_start_outside_and_end_inside():
    es = [ev(1, 10, "pass", outcome="success", location=(80, 34), end_location=(95, 34)),
          ev(2, 11, "carry", outcome="success", location=(85, 34), end_location=(92, 30)),
          ev(3, 12, "pass", outcome="success", location=(92, 30), end_location=(99, 34))]
    assert ask(calc(es), "box_entries") == 2


def test_met_006_007_008_shots_on_target_and_xg():
    es = [ev(1, 10, "shot", xg=0.3, shot_outcome="goal"), ev(2, 11, "shot", xg=0.1, shot_outcome="saved"),
          ev(3, 12, "shot", xg=0.05, shot_outcome="post"), ev(4, 13, "shot", xg=0.02, shot_outcome="blocked")]
    c = calc(es)
    assert (ask(c, "shots"), ask(c, "shots_on_target"), ask(c, "xg")) == (4, 2, 0.47)


def test_met_009_to_013_sums_and_counts():
    es = [ev(1, 10, "pass", outcome="success", threat=0.02), ev(2, 11, "carry", outcome="success", threat=-0.01),
          ev(3, 12, "pressure"), ev(4, 13, "tackle", outcome="success"), ev(5, 14, "tackle", outcome="fail"),
          ev(6, 15, "interception"), ev(7, 16, "duel", outcome="success", duel_type="aerial"),
          ev(8, 17, "duel", outcome="fail", duel_type="ground")]
    c = calc(es)
    assert ask(c, "threat_total") == 0.01
    assert (ask(c, "pressures"), ask(c, "tackles_won"), ask(c, "interceptions"), ask(c, "duels_won")) == (1, 1, 1, 1)


def test_met_014_turnovers_only_open_play_losses():
    es = [
        ev(1, 10, "pass", outcome="fail", possession_id=1, play_pattern="open_play"),
        ev(2, 12, "pass", team="away", outcome="success", possession_id=2, play_pattern="open_play"),
        ev(3, 20, "pass", outcome="success", possession_id=3, play_pattern="open_play"),
        ev(4, 22, "shot", xg=0.1, shot_outcome="saved", possession_id=3, play_pattern="open_play"),
        ev(5, 25, "pass", team="away", outcome="success", possession_id=4, play_pattern="open_play"),
        ev(6, 30, "pass", outcome="fail", possession_id=5, play_pattern="open_play"),
        ev(7, 40, "pass", team="away", outcome="success", possession_id=6, play_pattern="throw_in"),
    ]
    assert ask(calc(es), "turnovers") == 1                    # lost after a shot or to a throw-in do not count


def test_met_015_momentum_is_seen_from_each_side():
    es = [ev(1, 60 * m, "pass", outcome="success", threat=0.05) for m in range(1, 10)]
    c = calc(es)
    assert ask(c, "momentum_avg") > 0
    assert ask(c, "momentum_avg", team="away") == -ask(c, "momentum_avg")


def test_met_016_line_height_out_of_possession_uses_current_defenders():
    # h02-h05 are the 4-3-3 back four of the demo team; home defends the x = 0 goal.
    fs = [frame(0, "away", {"h02": (30, 60), "h03": (34, 43), "h04": (34, 25), "h05": (30, 8), "h09": (70, 34)}),
          frame(1, "home", {"h02": (60, 60), "h03": (60, 43), "h04": (60, 25), "h05": (60, 8)})]
    assert ask(calc(frames=fs), "line_height_m") == 32.0


def test_met_016_away_line_height_is_measured_from_its_own_goal():
    fs = [frame(0, "home", {"a02": (75, 60), "a03": (75, 43), "a04": (75, 25), "a05": (75, 8)})]
    assert ask(calc(frames=fs), "line_height_m", team="away") == 30.0


def test_met_017_width_in_possession_ignores_the_keeper():
    fs = [frame(0, "home", {"h01": (5, 0.5), "h02": (40, 60), "h05": (40, 8), "h09": (70, 34)})]
    assert ask(calc(frames=fs), "team_width_m") == 52.0


def test_met_018_press_distance_to_the_opponents_carrier():
    fs = [frame(0, "away", {"a09": (50, 34), "h06": (53, 38), "h08": (60, 34)}, owner="a09")]
    assert ask(calc(frames=fs), "press_distance_m") == 5.0


def test_met_019_distance_covered_adds_up_frame_steps():
    fs = [frame(t, "home", {"h07": (10 + 5 * (t % 2), 34)}) for t in range(101)]   # 5 m every second
    c = calc(frames=fs)
    assert ask(c, "distance_covered_km", player="h07") == 0.5
    assert ask(c, "distance_covered_km", window=(0, 1)) == 0.3        # only steps that start in minute 0


@pytest.mark.parametrize("start, end, expected", [
    ((20, 34), (49, 34), False), ((20, 34), (51, 34), True),     # own half: 30 m
    ((45, 34), (61, 34), True), ((45, 34), (59, 34), False),     # crossing halfway: 15 m
    ((60, 34), (71, 34), True), ((60, 34), (69, 34), False),     # opponent half: 10 m
])
def test_met_020_progressive_pass_thresholds(start, end, expected):
    e = ev(1, 10, "pass", outcome="success", location=start, end_location=end)
    assert StatCalculator.progressive(e) is expected


def test_met_021_ppda_in_the_opponents_build_up_zone():
    es = [ev(i, 10 + i, "pass", team="away", outcome="success", location=(80, 30)) for i in range(1, 10)]
    es += [ev(20, 40, "tackle", outcome="fail", location=(70, 30)), ev(21, 41, "interception", location=(65, 30)),
           ev(22, 42, "foul", location=(75, 30)), ev(23, 43, "duel", outcome="success", location=(30, 30))]
    assert ask(calc(es), "ppda") == 3.0        # 9 passes / 3 actions; the duel at x = 30 is outside the zone


def test_met_022_xa_credits_the_passer():
    p = ev(1, 10, "pass", player_id="h08", outcome="success", related_event_ids=["e2"])
    s = ev(2, 11, "shot", player_id="h09", xg=0.25, shot_outcome="saved", related_event_ids=["e1"])
    c = calc([p, s])
    assert ask(c, "xa") == 0.25
    assert ask(c, "xa", player="h08") == 0.25 and ask(c, "xa", player="h09") == 0.0


def test_met_023_field_tilt_shares_final_third_passes():
    es = [ev(1, 10, "pass", location=(80, 30), outcome="success"), ev(2, 11, "pass", location=(75, 30), outcome="fail"),
          ev(3, 12, "pass", location=(80, 30), outcome="success"),
          ev(4, 13, "pass", team="away", location=(20, 30), outcome="success")]
    assert ask(calc(es), "field_tilt_pct") == 75.0


def test_rat_001_idle_player_keeps_the_baseline_and_a_goal_adds_one():
    fs = [frame(t, "home", {"h09": (60, 34), "h10": (60, 20)}) for t in range(0, 1200)]
    es = [ev(1, 600, "shot", player_id="h09", xg=0.0, shot_outcome="goal")]
    stats = {s.player_id: s for s in player_match_stats(calc(es, fs))}
    forward = 6.5 + POSITION_OFFSET["FW"]                  # h09 and h10 are both forwards
    assert stats["h10"].rating == pytest.approx(forward)
    assert stats["h09"].rating == pytest.approx(forward + 1.0 + 0.1)   # goal + shot on target
    assert stats["h09"].minutes_played == 20


# --- on a simulated match -------------------------------------------------------------

@pytest.fixture(scope="module")
def sim_calc():
    return StatCalculator.from_sim(simulate(build_demo_match(1021)))


def test_possession_and_field_tilt_add_up_to_100(sim_calc):
    for metric in ("possession_pct", "field_tilt_pct"):
        assert ask(sim_calc, metric) + ask(sim_calc, metric, team="away") == pytest.approx(100, abs=0.2)


def test_team_totals_equal_the_sum_of_players(sim_calc):
    ids = [p.player_id for p in MATCH.home.squad]
    for metric in ("shots", "passes", "pressures", "interceptions"):
        assert ask(sim_calc, metric) == sum(ask(sim_calc, metric, player=pid) for pid in ids)


def test_numbers_are_in_football_ranges(sim_calc):
    assert 80 <= ask(sim_calc, "distance_covered_km") <= 130
    assert 10 <= ask(sim_calc, "line_height_m") <= 50
    assert 60 <= ask(sim_calc, "pass_accuracy_pct") <= 95
