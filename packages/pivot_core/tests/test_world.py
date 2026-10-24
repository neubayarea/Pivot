"""B13: the fictional league, its season, and the stories it gives the demo match (CTX-005)."""

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from pivot_core.sim import DEMO_1021, simulate
from pivot_core.sim.season import leads_lost, load_season, stakes, table, with_season
from pivot_core.sim.world import CLUBS, DEMO_MATCHDAY, club_team, schedule, with_careers

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures"


@pytest.fixture(scope="module")
def season():
    return load_season(FIXTURES)


@pytest.fixture(scope="module")
def demo(season):
    return with_season(DEMO_1021.build(), season)


def test_b13_demo_clubs_are_the_demo_squads_on_either_side():
    m = DEMO_1021.build()
    assert club_team("club-hbc", "home") == m.home
    assert club_team("club-rov", "away") == m.away
    rov_home = club_team("club-rov", "home")
    assert [p.attributes for p in rov_home.squad] == [p.attributes for p in m.away.squad]
    assert rov_home.squad[0].player_id == "h01"


def test_b13_schedule_is_a_double_round_robin_with_the_demo_on_matchday_30():
    fixtures = schedule()
    assert len(CLUBS) == 20 and len({c.name for c in CLUBS}) == 20
    assert set(Counter((f.home, f.away) for f in fixtures).values()) == {1} and len(fixtures) == 380
    for md in range(1, 39):
        assert len({x for f in fixtures if f.matchday == md for x in (f.home, f.away)}) == 20
    meetings = [(f.matchday, f.home, f.seed) for f in fixtures if {f.home, f.away} == {"club-hbc", "club-rov"}]
    assert meetings == [(11, "club-rov", 20261100), (DEMO_MATCHDAY, "club-hbc", DEMO_1021.seed)]


def test_b13_careers_are_deterministic_and_end_at_the_current_club():
    team = club_team("club-tes", "away")
    a, b = with_careers(team), with_careers(team)
    assert a == b
    for p in a.squad:
        assert p.career[-1].club_id == "club-tes" and p.career[-1].to_year is None
        assert all(s.to_year == t.from_year for s, t in zip(p.career, p.career[1:]))


def test_b13_season_file_covers_matchdays_before_the_demo(season):
    results = season["results"]
    assert len(results) == 10 * (DEMO_MATCHDAY - 1)
    assert {r["matchday"] for r in results} == set(range(1, DEMO_MATCHDAY))
    assert all(r["score"] == [sum(g[0] == r["home"] for g in r["goals"]), sum(g[0] == r["away"] for g in r["goals"])]
               for r in results)
    assert len(season["past_meetings"]) == 4


def test_ctx_005_table_and_stakes():
    results = [{"matchday": 1, "home": "club-hbc", "away": "club-rov", "score": [2, 1],
                "goals": [["club-hbc", 9, 10], ["club-rov", 9, 50], ["club-hbc", 10, 80]]},
               {"matchday": 2, "home": "club-rov", "away": "club-cor", "score": [1, 1],
                "goals": [["club-rov", 9, 10], ["club-cor", 9, 70]]}]
    rows = {r["club_id"]: r for r in table(results)}
    assert (rows["club-hbc"]["points"], rows["club-hbc"]["position"]) == (3, 1)
    assert rows["club-rov"]["points"] == 1 and rows["club-rov"]["drawn"] == 1
    assert stakes(table(results), ("club-hbc", "club-rov")) == "title_race"
    assert leads_lost(results, "club-rov") == (1, 2)          # led Corvale 1-0, drew 1-1
    assert leads_lost(results, "club-hbc") == (0, 0)


def test_ctx_005_demo_gets_form_table_head_to_head_and_news(demo):
    ctx = demo.context
    assert [f.side for f in ctx.form] == ["home", "away"]
    assert all(len(f.last_results) == 5 and f.league_position and f.points is not None for f in ctx.form)
    h2h = ctx.head_to_head
    assert h2h.played == 5 == h2h.home_wins + h2h.draws + h2h.away_wins
    assert [m.season for m in h2h.last_meetings] == ["2024", "2024", "2025", "2025", "2026"]
    assert 3 <= len(ctx.news) <= 5 and len({n.news_id for n in ctx.news}) == len(ctx.news)
    assert ctx.effects == []                                  # off-field factors do not touch play yet (B14)


def test_ctx_005_turning_points_carry_stories(demo):
    squad = {p.player_id: p for t in (demo.home, demo.away) for p in t.squad}
    assert any(s.club_id == "club-hbc" and s.departure_mood == "acrimonious" for s in squad["a04"].career[:-1])
    assert any(s.club_id == "club-rov" for s in squad["h13"].career[:-1])
    assert squad["h15"].career[-1].appearances == 99
    assert {"news-a04-return", "news-h15-100"} <= {n.news_id for n in demo.context.news}
    assert any(r.person_id == "a04" or r.other_id == "a04" for r in demo.context.relationships)


def _digest(out):
    return (hashlib.sha256(json.dumps(out.events, sort_keys=True, default=str).encode()).hexdigest(),
            hashlib.sha256(out.frames_pos.tobytes()).hexdigest())


def test_ctx_005_stories_do_not_change_the_demo_match(demo):
    plants = list(DEMO_1021.plants)
    assert _digest(simulate(demo, plants=plants)) == _digest(simulate(DEMO_1021.build(), plants=plants))
