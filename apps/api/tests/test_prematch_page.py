"""The pre-match numbers (Bx15, #314), checked against the season file and the context `with_seed_season` wrote."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from pivot_api import sims
from pivot_api.app import app
from pivot_api.prematch import PERIODS, PrematchReport, before, half_time, ht_score, matchday_of, prematch
from pivot_core.domain import LineupSlot, Match

SEASON = sims._season()
SEEDS = sims.SPECS[:4]


def seed(spec: sims.SimSpec):
    match = sims.seed_match(spec.seed, spec.home_strength, spec.away_strength, spec.home_formation,
                            spec.away_formation)
    return match.model_copy(update={"match_id": spec.match_id})


@pytest.fixture(scope="module")
def reports() -> dict[str, tuple]:
    return {spec.match_id: (m := seed(spec), prematch(m, SEASON)) for spec in SEEDS}


def test_the_matchday_is_the_one_with_seed_season_played_the_match_as(reports):
    """The table, form and head-to-head `with_seed_season` put in the context are those of our matchday."""
    for match, rep in reports.values():
        assert rep.matchday == matchday_of(match)
        for team, form in zip((rep.teams["home"], rep.teams["away"]), match.context.form):
            assert (team.overall.pts, team.overall.position) == (form.points, form.league_position)
            assert [g.result for g in reversed(team.last5)] == form.last_results
            assert sum(g.ft[0] for g in team.last5) == form.goals_for_last5
            assert sum(g.ft[1] for g in team.last5) == form.goals_against_last5
        h2h = match.context.head_to_head
        assert (rep.head_to_head.all.played, rep.head_to_head.all.home_w, rep.head_to_head.all.d,
                rep.head_to_head.all.away_w) == (h2h.played, h2h.home_wins, h2h.draws, h2h.away_wins)


def test_records_count_every_game_before_the_matchday_and_split_home_and_away(reports):
    for _, rep in reports.values():
        results = before(SEASON, rep.matchday)
        for team in rep.teams.values():
            mine = [r for r in results if team.club_id in (r["home"], r["away"])]
            assert team.overall.played == len(mine) == rep.matchday - 1
            home = [r for r in mine if r["home"] == team.club_id]
            assert team.home_only.played == len(home)
            assert team.home_only.gf == sum(r["score"][0] for r in home)
            assert team.home_only.ga == sum(r["score"][1] for r in home)
            for key in ("played", "w", "d", "l", "gf", "ga", "pts"):
                assert getattr(team.home_only, key) + getattr(team.away_only, key) == getattr(team.overall, key)
            assert [g.matchday for g in team.last5] == [r["matchday"] for r in mine[-5:]][::-1]


def test_half_time_scores_follow_the_goal_minutes_in_the_season_file():
    """Goals before the 46th elapsed minute are always first half, from the 50th always second half;
    the half-time score is never more than the final one."""
    for r in SEASON["results"] + SEASON["past_meetings"]:
        ht = half_time(r)
        assert 46 <= ht <= 49
        h, a = ht_score(r)
        assert h <= r["score"][0] and a <= r["score"][1]
        early = [g for g in r["goals"] if g[2] < 46]
        late = [g for g in r["goals"] if g[2] >= 49]
        assert h >= sum(g[0] == r["home"] for g in early) and a >= sum(g[0] == r["away"] for g in early)
        assert h + a <= len(r["goals"]) - len(late)


def test_form_stats_add_up(reports):
    for _, rep in reports.values():
        for team in rep.teams.values():
            s, games = team.last5_stats, team.last5
            assert s.games == len(games) == 5
            assert list(s.goals_by_period) == list(PERIODS)
            assert sum(s.goals_by_period.values()) == sum(g.ft[0] for g in games)
            assert sum(s.conceded_by_period.values()) == sum(g.ft[1] for g in games)
            assert s.clean_sheets == sum(g.ft[1] == 0 for g in games)
            assert s.btts == sum(min(g.ft) > 0 for g in games)
            assert s.ht_lead_won + s.ht_lead_dropped == sum(g.ht[0] > g.ht[1] for g in games)
            assert 4 < s.avg_rating < 9


def test_at_this_ground_counts_only_the_meetings_at_this_home_ground(reports):
    for match, rep in reports.values():
        meetings = rep.head_to_head.meetings
        here = [m for m in meetings if m.venue_club == match.home.club_id]
        assert rep.head_to_head.at_this_ground.played == len(here)
        assert rep.head_to_head.all.played == len(meetings)
        assert {m.season for m in meetings} >= {2024, 2025}       # the two seasons before are in the file
        for m in meetings:
            assert m.ht[0] <= m.ft[0] and m.ht[1] <= m.ft[1]


def test_the_usual_xi_is_counted_from_the_season_and_compared_with_today():
    """In the season file the starters are shirts 1-11 every game, so the usual XI all start today;
    take one off the sheet and the report says so."""
    match = seed(SEEDS[0])
    rep = prematch(match, SEASON)
    xi = rep.teams["home"].usual_xi_today
    assert (xi.regulars_starting, xi.regulars_benched, xi.newcomers) == (11, [], [])
    assert rep.teams["home"].next_fixture.rotation_note.endswith("The usual starting XI all start today.")
    sheet = match.home.sheet
    out, sub = sheet.starters[9], sheet.bench[0]
    starters = [*sheet.starters[:9], LineupSlot(player_id=sub, slot=out.slot, role=out.role, anchor=out.anchor),
                *sheet.starters[10:]]
    home = match.home.model_copy(update={"sheet": sheet.model_copy(update={"starters": starters,
                                                                         "bench": [out.player_id, *sheet.bench[1:]]})})
    xi = prematch(match.model_copy(update={"home": home}), SEASON).teams["home"].usual_xi_today
    assert (xi.regulars_starting, xi.regulars_benched, xi.newcomers) == (10, [out.player_id], [sub])


def test_next_fixtures_come_from_the_schedule_and_the_seed(reports):
    for match, rep in reports.values():
        cups = [t.next_fixture.opponent_id for t in rep.teams.values() if t.next_fixture.fictional]
        assert len(cups) == len(set(cups))                         # two clubs never draw the same opponent
        for team in rep.teams.values():
            league = team.next_league
            assert league.matchday == rep.matchday + 1 and not league.fictional
            assert league.opponent_id != team.club_id
            nf = team.next_fixture
            assert nf.fictional == (nf.competition == "Freeland Cup")
            assert nf.rotation_risk in ("low", "medium", "high")
        again = prematch(match, SEASON)
        assert again == rep                                         # the same seed, the same report


def test_matchup_lines_and_tactics_speak_for_the_side_asked(reports):
    match, rep = reports["M-seed-101"]
    away = prematch(match, SEASON, "away")
    assert rep.matchup.perspective == "home" and away.matchup.perspective == "away"
    zones = {line.zone: line for line in rep.matchup.lines}
    assert set(zones) == {"home_wide_left", "home_wide_right", "midfield", "home_attack", "away_attack"}
    starters = {s.player_id for s in match.home.sheet.starters}
    assert all(p in starters for line in rep.matchup.lines for p in line.home_players)
    assert zones["home_attack"].away == ["CB"] * len(zones["home_attack"].away)
    for line, other in zip(rep.matchup.lines, away.matchup.lines):
        assert (line.home, line.away) == (other.home, other.away)    # the same lines, told from the other side
    flank = {line.zone: line.params["flank"] for line in away.matchup.lines if "flank" in line.params}
    assert flank == {"home_wide_left": "right", "home_wide_right": "left"}
    fields = [d.field for d in rep.matchup.tactics_diff]
    assert fields, "#289 gives the two coaches different tactics"
    for d in rep.matchup.tactics_diff:
        assert d.home == str(getattr(match.home.tactics, d.field)).lower() != d.away
        assert match.home.name in d.note and d.note_key.startswith("prematch.tactics.")
    assert [d.field for d in away.matchup.tactics_diff] == fields


def test_the_recorded_demo_is_matchday_30_and_agrees_with_its_context():
    demo = Match.model_validate(json.loads(sims.FIXTURE.read_text(encoding="utf-8"))["match"])
    rep = prematch(demo, SEASON)
    assert rep.matchday == 30
    for team, form in zip((rep.teams["home"], rep.teams["away"]), demo.context.form):
        assert (team.overall.pts, team.overall.position) == (form.points, form.league_position)
        assert [g.result for g in reversed(team.last5)] == form.last_results


def test_other_matches_have_no_matchday():
    match = seed(SEEDS[0])
    other = match.model_copy(update={"away": match.away.model_copy(update={"club_id": "club-cor"})})
    assert matchday_of(other) is None and prematch(other, SEASON) is None


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PIVOT_DEMO_FIXTURE", str(sims.FIXTURE))
    monkeypatch.setenv("PIVOT_SIM_MATCHES", "0")
    monkeypatch.setenv("PIVOT_WHATIF_WARM", "0")
    monkeypatch.setenv("PIVOT_PREWARM_LANGS", "none")
    with TestClient(app) as c:
        yield c


def test_the_endpoint_serves_the_recorded_demo_as_matchday_30(client):
    match_id = json.loads(sims.FIXTURE.read_text(encoding="utf-8"))["match"]["match_id"]
    r = client.get(f"/api/matches/{match_id}/prematch", params={"team": "away"})
    assert r.status_code == 200, r.text
    rep = PrematchReport.model_validate(r.json())
    assert rep.matchday == 30 and rep.matchup.perspective == "away"
    assert rep.teams["home"].overall.played == 29
    assert client.get(f"/api/matches/{match_id}/prematch", params={"team": "both"}).status_code == 422
    assert client.get("/api/matches/no-such-match/prematch").status_code == 404
