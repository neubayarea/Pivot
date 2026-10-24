"""Momentum alarm (B06, ADR-0010)."""

import numpy as np

from pivot_core.analytics import DetectorParams, PivotDetector, detect_candidates, key_events, momentum_series
from pivot_core.domain import FoulDetail, MatchEvent, MinuteMetric
from pivot_core.sim import build_demo_match, simulate

MID = "M-test"


def series(values, start=0):
    return [MinuteMetric(match_id=MID, minute=start + i, momentum=float(v), threat_home=0, threat_away=0,
                         pressure_home=0, pressure_away=0) for i, v in enumerate(values)]


def ev(seq, minute, type_, team="home", **kw):
    t = minute * 60 + 5
    return MatchEvent(match_id=MID, seq=seq, event_id=f"e{seq}", t=t, period=1 if t < 2700 else 2,
                      period_t=t if t < 2700 else t - 2700, type=type_, team=team, **kw)


def noise(n, rng, sd=0.05):
    return rng.normal(0, sd, n)


def test_a_clear_swing_to_the_away_side_raises_one_alarm_near_the_change():
    rng = np.random.default_rng(0)
    values = np.r_[0.4 + noise(30, rng), -0.4 + noise(15, rng)]
    found = detect_candidates(MID, series(values), [])
    assert len(found) == 1
    assert found[0].direction == "away" and 29 <= found[0].minute <= 32
    assert found[0].swing < -0.3


def test_ordinary_wobble_raises_nothing():
    rng = np.random.default_rng(1)
    assert detect_candidates(MID, series(noise(45, rng, sd=0.08)), []) == []


def test_a_swing_that_does_not_hold_is_dropped():
    rng = np.random.default_rng(2)
    values = np.r_[0.3 + noise(25, rng), -0.5 + noise(2, rng), 0.3 + noise(18, rng)]
    assert detect_candidates(MID, series(values), []) == []


def test_candidates_are_at_least_8_minutes_apart_and_at_most_5():
    values = np.tile(np.r_[np.full(6, 0.5), np.full(6, -0.5)], 8)
    found = detect_candidates(MID, series(values), [], DetectorParams(min_swing=0.2))
    minutes = [c.minute for c in found]
    assert len(found) <= 5
    assert all(b - a >= 8 for a, b in zip(minutes, minutes[1:]))


def test_live_detector_confirms_five_minutes_after_the_change():
    rng = np.random.default_rng(0)
    values = np.r_[0.4 + noise(30, rng), -0.4 + noise(15, rng)]
    det = PivotDetector(MID)
    confirmed_at = None
    for m in series(values):
        if det.push(m) and confirmed_at is None:
            confirmed_at = m.minute
    assert confirmed_at is not None
    assert confirmed_at - det.emitted[0].minute == 4         # minutes c .. c+4 are the five after it


def test_window_and_key_events_for_the_judge():
    rng = np.random.default_rng(0)
    values = np.r_[0.4 + noise(30, rng), -0.4 + noise(15, rng)]
    events = [ev(1, 29, "shot", team="away", shot_outcome="goal", xg=0.3),
              ev(2, 28, "card", foul=FoulDetail(foul_type="tackle", card="yellow")),
              ev(3, 27, "card", foul=FoulDetail(foul_type="tackle", card="red")),
              ev(4, 10, "substitution")]
    c = detect_candidates(MID, series(values), events)[0]
    assert c.window == (c.minute - 8, c.minute + 5)
    assert c.key_event_ids == ["e1", "e3"]                    # goal and red card; yellow and early sub left out
    assert key_events(events, (0, 90)) == ["e1", "e3", "e4"]


def test_simulated_matches_give_a_few_candidates_each():
    counts = []
    for seed in (11, 12, 13, 14, 15):
        out = simulate(build_demo_match(seed))
        events = out.events_as_models()
        found = detect_candidates(out.match.match_id, momentum_series(out.match.match_id, events), events)
        counts.append(len(found))
        assert all(c.direction in ("home", "away") for c in found)
    assert 1 <= np.mean(counts) <= 5
