"""B10 acceptance: any player's own numbers can be read (tasks.csv, issue #59).

Two places answer for one player: the StatCalculator (B05) when a StatRef carries `player_id`,
and `player_match_stats`, which gives every player who played a stat line and a rating. Both
are checked on the planted demo match, which has a red card and several substitutions.
"""

import math
import typing

import pytest

from pivot_core.analytics import StatCalculator, player_match_stats
from pivot_core.analytics.stats import MAX_STEP_M
from pivot_core.domain import StatMetric, StatRef
from pivot_core.sim import DEMO_1021, simulate

TEAM_ONLY = {"possession_pct", "momentum_avg", "team_width_m", "ppda", "field_tilt_pct"}
PLAYER_METRICS = [m for m in typing.get_args(StatMetric) if m not in TEAM_ONLY]


@pytest.fixture(scope="module")
def calc():
    return StatCalculator.from_sim(simulate(DEMO_1021.build(), plants=list(DEMO_1021.plants)))


@pytest.fixture(scope="module")
def lines(calc):
    return {s.player_id: s for s in player_match_stats(calc)}


@pytest.fixture(scope="module")
def sent_off(calc):
    return next(e for e in calc.events if e.type == "card" and e.foul.card in ("red", "second_yellow"))


@pytest.fixture(scope="module")
def came_on(calc):
    return next(e for e in calc.events if e.type == "substitution")


def ask(calc, metric, pid, window=(0, 120)):
    return calc.compute(StatRef(metric=metric, team=calc.team_of[pid], window=window, player_id=pid))


def test_b10_everyone_who_played_has_a_stat_line(calc, lines):
    played = set(calc._frames.pos)
    assert set(lines) == played
    bench = {p.player_id for t in (calc.match.home, calc.match.away) for p in t.squad} - played
    assert bench and not bench & set(lines)                # an unused substitute has no line


def test_b10_every_player_metric_answers_for_any_player_who_played(calc, lines):
    for pid, line in lines.items():
        for metric in PLAYER_METRICS:
            if metric == "pass_accuracy_pct" and line.passes == 0:
                with pytest.raises(LookupError):
                    ask(calc, metric, pid)
                continue
            try:
                value = ask(calc, metric, pid)
            except LookupError:
                # a late substitute can be on only while his side has the ball: no defending numbers
                assert line.minutes_played <= 10, (pid, metric)
                continue
            assert math.isfinite(value) and (value >= 0 or metric == "threat_total"), (pid, metric)


@pytest.mark.parametrize("who", ["starter", "substitute", "sent_off"])
def test_b10_stat_line_matches_the_stat_calculator(calc, lines, came_on, sent_off, who):
    pid = {"starter": "h05", "substitute": came_on.substitution.player_on_id, "sent_off": sent_off.player_id}[who]
    line = lines[pid]
    for metric, value in (("shots", line.shots), ("passes", line.passes), ("tackles_won", line.tackles_won),
                          ("interceptions", line.interceptions), ("duels_won", line.duels_won),
                          ("progressive_passes", line.progressive_passes),
                          ("distance_covered_km", line.distance_km)):
        assert ask(calc, metric, pid) == value, metric
    assert ask(calc, "xg", pid) == pytest.approx(line.xg, abs=0.005)
    assert ask(calc, "xa", pid) == pytest.approx(line.xa, abs=0.005)


def test_b10_substitute_counts_only_from_coming_on(calc, lines, came_on):
    pid = came_on.substitution.player_on_id
    on_minute = came_on.t // 60
    assert ask(calc, "passes", pid, window=(0, on_minute)) == 0
    with pytest.raises(LookupError):                       # no frames before coming on
        ask(calc, "distance_covered_km", pid, window=(0, on_minute))
    last_minute = int(calc._frames.t.max()) // 60
    assert abs(lines[pid].minutes_played - (last_minute - on_minute)) <= 2


def test_b10_sent_off_player_stops_at_the_card(calc, lines, sent_off):
    pid, card_minute = sent_off.player_id, sent_off.t // 60
    assert abs(lines[pid].minutes_played - card_minute) <= 1
    assert lines[pid].rating < 6.5                          # the red card costs 1.5
    after = (card_minute + 1, 120)
    assert ask(calc, "passes", pid, window=after) == 0
    with pytest.raises(LookupError):
        ask(calc, "line_height_m", pid, window=after)


def test_b10_top_speed_leaves_out_the_half_time_walk_back(lines):
    # Before the fix every outfielder's top speed was the jump back to their own half for the
    # second-half kick-off, often the 45 km/h cap.
    assert max(s.top_speed_kmh for s in lines.values()) <= MAX_STEP_M * 3.6
    assert all(s.distance_km < 13 for s in lines.values())
