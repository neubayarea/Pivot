"""Bx13: a simulated match the site stores carries its pre-match context, and the events, score and
frames stored with it are exactly what the engine produced."""

from pivot_api import sims
from pivot_core.domain import Match, MatchEvent
from pivot_core.sim import simulate as real_simulate

SPEC = sims.SPECS[0]


def test_build_one_stores_the_played_match_with_its_pre_match_context(tmp_path, monkeypatch):
    played = {}

    def simulate(match):
        played["out"] = out = real_simulate(match)
        return out

    monkeypatch.setattr(sims, "simulate", simulate)
    assert sims.build_one(SPEC, tmp_path)
    data_path, frames_path = sims.paths(tmp_path, SPEC)
    data = sims._read_json_gz(data_path)
    out = played["out"]

    # the match as played: every event, the score, the periods and every frame are the engine's own
    assert data["events"] == [e.model_dump(mode="json", round_trip=True) for e in out.events_as_models()]
    assert sims.read_frames(frames_path) == [f.model_dump(mode="json") for f in out.frames_as_models()]
    stored = Match.model_validate(data["match"])
    assert stored.score == out.match.score and stored.periods == out.match.periods
    assert stored.home.sheet == out.match.home.sheet and stored.home.tactics == out.match.home.tactics

    # and what the pre-match page shows
    c = stored.context
    assert len(c.form) == 2 and c.head_to_head and c.head_to_head.played >= 4
    assert 3 <= len(c.news) <= 6 and c.relationships and c.effects
    assert c == sims.prematch(out.match, SPEC).context            # the same every time for this seed
    assert [MatchEvent.model_validate(e) for e in data["events"]] == out.events_as_models()


def test_without_the_season_file_the_match_keeps_the_basic_context(monkeypatch, tmp_path):
    monkeypatch.setattr(sims, "FIXTURE", tmp_path / "missing" / "demo-1021.json")
    sims._season.cache_clear()
    try:
        match = sims.build_demo_match(SPEC.seed)
        assert sims.prematch(match, SPEC) == match
    finally:
        sims._season.cache_clear()
