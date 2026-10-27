"""Set-piece positions (Ax44, #245): where players stand at corners and free kicks, and the kick
played from there."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from pivot_core.sim import DEMO_1021, build_demo_match, simulate

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from realism_scorecard import setpiece_rows  # noqa: E402

SEEDS = (1000, 1001, 1002, 1003)


@pytest.fixture(scope="module")
def outs():
    return [simulate(build_demo_match(s)) for s in SEEDS]


@pytest.fixture(scope="module")
def rows(outs):
    return [setpiece_rows(o) for o in outs]


def _kick_frames(out, kind: str):
    """(frame index, attacking side, taker id) at the frame before each corner or free-kick pass."""
    side = {"home": 0, "away": 1}
    for e in out.events:
        if e["type"] == "pass" and e.get("pass_type") == kind:
            n = int(np.searchsorted(out.frames_t, e["t"])) - 1
            if n >= 0:
                yield n, side[e["team"]], e["player_id"]


def test_ax44_same_seed_same_positions():
    a = simulate(build_demo_match(1000))
    b = simulate(build_demo_match(1000))
    assert np.array_equal(a.frames_pos, b.frames_pos)
    assert np.array_equal(a.frames_speed, b.frames_speed)


def test_ax44_demo_match_events_as_recorded():
    """The demo match (seed 29) plays event for event as the recorded fixture (scripts/make_demo.py)."""
    recorded = json.loads((ROOT / "eval" / "fixtures" / "demo-1021.json").read_text(encoding="utf-8"))
    out = simulate(DEMO_1021.build(), plants=list(DEMO_1021.plants))
    fresh = [e.model_dump(mode="json", exclude_none=True) for e in out.events_as_models()]
    assert len(fresh) == len(recorded["events"])
    keys = ("event_id", "t", "type", "team", "player_id", "outcome", "shot_outcome", "pass_type")
    for a, b in zip(fresh, recorded["events"]):
        assert {k: a.get(k) for k in keys} == {k: b.get(k) for k in keys}
    assert (out.match.score.home, out.match.score.away) == (recorded["match"]["score"]["home"],
                                                            recorded["match"]["score"]["away"])


def test_ax44_opponents_9_15_m_from_the_ball_at_every_free_kick_and_corner(outs):
    checked = 0
    for out in outs:
        for kind in ("free_kick", "corner"):
            for n, k, _ in _kick_frames(out, kind):
                ball = out.frames_ball[n][:2]
                ids = out.frames_ids[n][1 - k]
                d = np.sqrt(((out.frames_pos[n, 1 - k] - ball) ** 2).sum(-1))
                assert all(dist >= 9.15 for dist, pid in zip(d, ids) if pid), (kind, out.frames_t[n])
                checked += 1
    assert checked > 50


def test_ax44_corner_box_counts_like_the_premier_league(rows):
    corners = [r for m in rows for r in m["corners"]]
    assert len(corners) > 20
    att = np.array([r["att_box"] for r in corners])
    dfn = np.array([r["def_box"] for r in corners])
    # PL 2015/16 freeze frames: 5.3 attackers (4-6) and 8.6 defenders (7-10) in the box
    assert 4.5 <= att.mean() <= 6.0 and 7.5 <= dfn.mean() <= 9.5
    assert np.mean((att >= 3) & (att <= 7)) > 0.95 and np.mean((dfn >= 6) & (dfn <= 10)) > 0.95
    assert all(r["keeper_m"] <= 3.0 for r in corners if "keeper_m" in r)


def test_ax44_wall_size_falls_with_distance(rows):
    fks = [r for m in rows for r in m["free_kicks"] if r["dist"] < 32 and r["wide"] < 18]
    close = [r["wall_line"] for r in fks if r["dist"] < 25]
    far = [r["wall_line"] for r in fks if r["dist"] >= 25]
    assert close and far
    assert np.mean(close) >= 4 and np.mean(far) <= np.mean(close) - 1
    assert all(9.15 <= r["wall_m"] <= 10.5 for r in fks if "wall_m" in r)


def test_ax44_the_man_on_the_ball_is_shown_on_it(outs):
    """Whoever has the ball is where the ball is, set piece or not."""
    on_ball = off = 0
    for out in outs:
        for n, pid in enumerate(out.frames_owner):
            for k in (0, 1):
                if pid and pid in out.frames_ids[n][k]:
                    i = out.frames_ids[n][k].index(pid)
                    on_ball += 1
                    off += float(np.sqrt(((out.frames_pos[n, k, i] - out.frames_ball[n][:2]) ** 2).sum())) > 2.0
    assert off / on_ball < 0.005
