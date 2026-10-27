"""Bx13: the site's simulated matches get the full pre-match context (CTX-005, CTX-006) after they are
played, so the match itself does not change."""

from pathlib import Path

import pytest

from pivot_core.sim import DEMO_1021, build_demo_match
from pivot_core.sim.season import SITE_ROUNDS, load_season, site_matchday, with_prematch, with_season

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures"
STORY = {"former_club", "rivalry", "off_field"}


@pytest.fixture(scope="module")
def season():
    return load_season(FIXTURES)


def test_ctx_005_each_site_seed_gets_a_round_of_the_same_season():
    assert [site_matchday(s) for s in (101, 212, 303, 1010)] == [22, 23, 24, 21]
    assert all(site_matchday(s) in SITE_ROUNDS for s in range(500))
    assert set(SITE_ROUNDS) == set(range(21, 31))


@pytest.mark.parametrize("seed, strengths, formations", [(101, (72, 70), ("4-3-3", "4-2-3-1")),
                                                         (505, (74, 69), ("3-5-2", "4-3-3"))])
def test_ctx_005_a_site_match_gets_form_table_head_to_head_news_ties_and_effects(season, seed, strengths, formations):
    match = build_demo_match(seed, *strengths, *formations)
    m = with_prematch(match, season, site_matchday(seed))
    c = m.context
    assert [f.side for f in c.form] == ["home", "away"]
    assert all(len(f.last_results) == 5 and f.league_position and f.points for f in c.form)
    assert c.head_to_head.played >= 4 and c.stakes != "none"
    assert 3 <= len(c.news) <= 6
    side = {p.player_id: t.side for t in (m.home, m.away) for p in t.squad}
    across = [r for r in c.relationships if side[r.person_id] != side[r.other_id]]
    assert len(across) >= 2
    assert sum(e.source in STORY for e in c.effects) >= 2 and c.conditions
    # what the simulator reads is untouched: squads' ratings, sheets, tactics, the rest of the context
    assert m.context.competition == match.context.competition and m.context.referee == match.context.referee
    assert m.home.sheet == match.home.sheet and m.home.tactics == match.home.tactics
    assert [p.attributes for p in m.home.squad] == [p.attributes for p in match.home.squad]
    assert with_prematch(match, season, site_matchday(seed)) == m        # the same every time


def test_ctx_005_rounds_differ_but_come_from_one_season(season):
    match = build_demo_match(101)
    tables = {md: [(f.league_position, f.points) for f in with_season(match, season, md).context.form] for md in (21, 25, 30)}
    assert len({tuple(t) for t in tables.values()}) == 3
    assert tables[21][0][1] < tables[25][0][1] < tables[30][0][1]       # points only go up through the season


def test_ctx_005_the_demo_still_gets_round_30(season):
    demo = DEMO_1021.build()
    assert with_season(demo, season) == with_season(demo, season, 30)
