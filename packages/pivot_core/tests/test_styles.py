"""Bx13: coach styles give the two sides different plans, chosen from the seed, without touching the squads."""

from collections import Counter

from pivot_core.domain import TeamTactics
from pivot_core.sim import build_demo_match
from pivot_core.sim.styles import STYLES, style_of, with_coach_styles


def test_styles_come_from_the_seed_and_leave_the_squads_alone():
    base = build_demo_match(101)
    styled = with_coach_styles(base)
    assert styled == with_coach_styles(build_demo_match(101))           # the same every time
    for side in ("home", "away"):
        a, b = getattr(base, side), getattr(styled, side)
        assert a.squad == b.squad and a.sheet == b.sheet and a.coach.name == b.coach.name
        coach_style, tactics, _ = STYLES[style_of(101, side)]
        assert b.coach.style == coach_style
        assert all(getattr(b.tactics, k) == v for k, v in tactics.items())
    assert styled.context == base.context and styled.seed == base.seed


def test_styles_vary_across_matches_and_between_the_two_sides():
    pairs = [(style_of(s, "home"), style_of(s, "away")) for s in range(1, 301)]
    seen = Counter(s for pair in pairs for s in pair)
    assert set(seen) == set(STYLES) and min(seen.values()) > 60      # every style turns up, none dominates
    assert sum(h != a for h, a in pairs) > 200                       # usually the two coaches differ


def test_every_style_is_a_valid_plan_and_most_differ_from_the_default():
    default = TeamTactics()
    for name, (coach, tactics, set_pieces) in STYLES.items():
        tac = TeamTactics(**tactics)
        assert coach in ("defensive", "balanced", "attacking")
        assert (tac == default) == (name == "balanced")
        assert not set(set_pieces) - set(type(default.set_pieces).model_fields)
