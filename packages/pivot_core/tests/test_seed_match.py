"""Bx13: the site's seed matches get each coach's own tactics and the pre-match context of the season."""

from pathlib import Path

import pytest

from pivot_core.domain import TeamTactics
from pivot_core.sim import DEMO_1021, build_demo_match
from pivot_core.sim.season import load_season, with_seed_season
from pivot_core.sim.tactics import STYLES, styled

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures"
SEEDS = [101 * k for k in range(1, 21)]           # the site's twenty seeds (pivot_api.sims.specs_first)
PLAN = ("line_height", "press", "width", "tempo", "passing", "attack_focus", "set_pieces")


@pytest.fixture(scope="module")
def season():
    return load_season(FIXTURES)


def test_bx13_tactics_follow_the_coach_style_and_are_the_same_every_time():
    for seed in SEEDS:
        m = styled(build_demo_match(seed))
        assert m == styled(build_demo_match(seed))
        for team in (m.home, m.away):
            style, tac = team.coach.style, team.tactics
            assert style in STYLES
            if style == "defensive":
                assert tac.line_height in ("low", "mid") and tac.press in ("low", "mid") and tac.tempo == "slow"
                assert tac.counter_attack and tac.set_pieces.corner_defence == "zonal"
            elif style == "attacking":
                assert tac.line_height in ("high", "mid") and tac.press in ("high", "mid") and tac.passing == "short"
                assert tac.set_pieces.corner_defence == "man"
            else:
                assert (tac.line_height, tac.press, tac.tempo) == ("mid", "mid", "normal")


def test_bx13_two_teams_usually_play_differently():
    differ = 0
    for seed in SEEDS:
        m = styled(build_demo_match(seed))
        differ += any(getattr(m.home.tactics, k) != getattr(m.away.tactics, k) for k in PLAN)
    assert differ >= 18
    styles = {styled(build_demo_match(seed)).home.coach.style for seed in SEEDS}
    assert styles == set(STYLES)


def test_bx13_the_demo_keeps_the_default_tactics():
    m = DEMO_1021.build()
    assert m.home.tactics == m.away.tactics == TeamTactics() and m.home.coach.style == "balanced"


def test_bx13_seed_matches_get_the_full_pre_match_context(season):
    for seed in (101, 212, 303):
        m = with_seed_season(styled(build_demo_match(seed)), season)
        assert m == with_seed_season(styled(build_demo_match(seed)), season)
        ctx = m.context
        assert [f.side for f in ctx.form] == ["home", "away"]
        assert all(f.last_results and f.league_position for f in ctx.form)
        assert ctx.head_to_head and ctx.head_to_head.played >= 4
        assert 2 <= len(ctx.news) <= 5 and ctx.relationships and ctx.conditions and ctx.effects
        assert all(len(p.career) >= 1 for t in (m.home, m.away) for p in t.squad)
        people = {p.player_id for t in (m.home, m.away) for p in t.squad} | {m.home.coach.coach_id,
                                                                               m.away.coach.coach_id}
        assert {n.subject_id for n in ctx.news} <= people
    contexts = [with_seed_season(styled(build_demo_match(s)), season).context for s in (101, 212, 303)]
    assert len({tuple(f.points for f in c.form) for c in contexts}) > 1     # a different matchday each


def test_bx13_an_away_starter_once_played_for_the_home_club(season):
    m = with_seed_season(build_demo_match(212), season)
    back = next(n for n in m.context.news if n.news_id.endswith("-return"))
    player = next(p for p in m.away.squad if p.player_id == back.subject_id)
    assert player.career[-2].club_id == m.home.club_id and player.career[-1].club_id == m.away.club_id
    assert any(e.source == "former_club" and e.subject_id == player.player_id for e in m.context.effects)
