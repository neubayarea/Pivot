import importlib.util
import json
import typing
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from pivot_core.domain import (
    STAT_UNITS,
    Claim,
    ExplanationSentence,
    Match,
    MatchEvent,
    Narrative,
    Pivot,
    Player,
    PlayerAttributes,
    StatMetric,
    StatRef,
    Team,
    TrackingFrame,
    ViewerPrefs,
    zone_of,
)

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "packages/contracts/schema/pivot.schema.json").read_text(encoding="utf-8"))


def validate(name: str, data: dict) -> None:
    """Validate serialized output against one definition of the exported schema."""
    jsonschema.validate(data, {**SCHEMA, "$ref": f"#/$defs/{name}"})


ATTRS = PlayerAttributes(pace=78, passing=72, dribbling=70, shooting=65, defending=40,
                         physical=66, stamina=80)


def team(side: str, name: str, short: str) -> Team:
    prefix = side[0]
    return Team(
        side=side, name=name, short_name=short, color="#1E6B45", formation="4-3-3",
        players=[Player(player_id=f"{prefix}{n}", name=f"Player {n}", team=side, shirt_number=n,
                        role=role, attributes=ATTRS) for n, role in ((7, "RW"), (9, "ST"), (6, "DM"))],
    )


def sentence(text: str, value: float, prefs_metric: str = "shots") -> ExplanationSentence:
    return ExplanationSentence(
        text=text, evidence_ids=["m061-s01012", "m063-s01042"],
        claims=[Claim(value=value, unit="count",
                      stat_ref=StatRef(metric=prefs_metric, team="away", window=(63, 68)))],
    )


@pytest.fixture
def pivot() -> Pivot:
    return Pivot(
        pivot_id="M-seed-20261021:p63", match_id="M-seed-20261021", minute=63, direction="away",
        severity=2, status="confirmed", trigger_event_ids=["m063-s01042"], chain_id="c-1",
        narrative=Narrative(
            prefs=ViewerPrefs(), headline="Rovers seize control after the change",
            sentences=[sentence("Rovers took 4 shots in five minutes after the substitution.", 4)],
            source="llm", verifier_attempts=1,
        ),
    )


def test_stat_vocabulary_has_19_metrics_each_with_a_unit():
    metrics = typing.get_args(StatMetric)
    assert len(metrics) == 19
    assert set(STAT_UNITS) == set(metrics)


def test_event_minute_and_zones_are_derived():
    e = MatchEvent(match_id="M", seq=1042, event_id="m062-s01042", t=3750, period=2,
                   type="pass", team="home", player_id="h07", receiver_id="h09",
                   location=(64.2, 30.1), end_location=(88.0, 34.5), outcome="success",
                   ball_speed_kmh=52.0, under_pressure=True, possession_id=118,
                   play_pattern="counter")
    data = e.model_dump(mode="json")
    assert (data["minute"], data["from_zone"], data["to_zone"]) == (62, [7, 3], [10, 4])
    validate("MatchEvent", data)


def test_zone_of_clamps_the_far_touchline_and_goal_line():
    assert zone_of((0.0, 0.0)) == (0, 0)
    assert zone_of((105.0, 68.0)) == (11, 7)


def test_a_goal_is_a_shot_with_outcome_goal():
    e = MatchEvent(match_id="M", seq=7, event_id="m038-s00007", t=2290, period=1, type="shot",
                   team="away", player_id="a09", location=(14.0, 33.0), end_location=(0.0, 34.2),
                   shot_outcome="goal", xg=0.31, ball_speed_kmh=96.5)
    validate("MatchEvent", e.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        MatchEvent(match_id="M", seq=8, event_id="x", t=1, period=1, type="goal", team="home")


def test_tracking_frame_holds_at_most_22_players_inside_the_pitch():
    frame = TrackingFrame(
        match_id="M", t=3750, period=2, possession="home",
        ball={"x": 64.2, "y": 30.1, "owner_id": "h07"},
        players=[{"player_id": f"h{n}", "x": 50.0 + n, "y": 30.0, "speed_ms": 4.2} for n in range(1, 12)],
    )
    validate("TrackingFrame", frame.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        TrackingFrame(match_id="M", t=1, period=1, possession=None, ball={"x": 106.0, "y": 0.0}, players=[])
    with pytest.raises(ValidationError):
        TrackingFrame(match_id="M", t=1, period=1, possession=None, ball={"x": 52.5, "y": 34.0},
                      players=[{"player_id": f"p{n}", "x": 1.0, "y": 1.0} for n in range(23)])


def test_full_time_event_stays_in_minute_89():
    e = MatchEvent(match_id="M", seq=1, event_id="m089-s00001", t=5400, period=2,
                   type="period_end", team="home")
    assert e.minute == 89


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        ViewerPrefs(audience="fan", colour="red")


def test_sentence_needs_one_to_four_evidence_ids():
    with pytest.raises(ValidationError):
        ExplanationSentence(text="No evidence.", evidence_ids=[])
    with pytest.raises(ValidationError):
        ExplanationSentence(text="Too much.", evidence_ids=[f"e{i}" for i in range(5)])


def test_viewer_prefs_default_to_analyst_in_english():
    p = ViewerPrefs()
    assert (p.audience, p.language, p.focus_team, p.focus_player_id) == ("analyst", "en", None, None)


def test_pivot_round_trips_and_matches_the_exported_schema(pivot: Pivot):
    data = pivot.model_dump(mode="json")
    assert Pivot.model_validate(data) == pivot
    validate("Pivot", data)


def test_fan_version_keeps_the_same_evidence_and_numbers(pivot: Pivot):
    analyst = pivot.narrative
    fan = analyst.model_copy(update={
        "prefs": ViewerPrefs(audience="fan", language="zh", focus_team="away"),
        "headline": "换人之后，Rovers 接管了比赛",
        "sentences": [sentence("换人后的五分钟里，Rovers 射门 4 次。", 4)],
    })
    validate("Narrative", fan.model_dump(mode="json"))
    claims = lambda n: [c for s in n.sentences for c in s.claims]  # noqa: E731
    assert claims(fan) == claims(analyst)
    assert fan.sentences[0].evidence_ids == analyst.sentences[0].evidence_ids


def test_player_position_group_follows_the_role():
    players = team("home", "Harbour City", "HBC").players
    assert [p.position for p in players] == ["FW", "FW", "MF"]
    assert players[0].model_dump()["position"] == "FW"


def test_ratings_stay_between_1_and_99():
    with pytest.raises(ValidationError):
        PlayerAttributes(**{**ATTRS.model_dump(), "pace": 120})


def test_pass_carries_difficulty_type_height_and_links():
    e = MatchEvent(match_id="M", seq=1041, event_id="m062-s01041", t=3749, period=2, type="pass",
                   team="home", player_id="h06", receiver_id="h09", location=(48.0, 34.0),
                   end_location=(86.0, 30.0), outcome="success", success_prob=0.38,
                   pass_type="through_ball", pass_height="ground", body_part="right_foot",
                   ball_speed_kmh=61.0, related_event_ids=["m062-s01042"])
    data = e.model_dump(mode="json")
    assert data["related_event_ids"] == ["m062-s01042"]
    validate("MatchEvent", data)
    with pytest.raises(ValidationError):
        MatchEvent(**{**e.model_dump(exclude={"minute", "from_zone", "to_zone"}), "success_prob": 1.2})


def test_match_serializes_defaults():
    m = Match(match_id="M-seed-20261021", seed=20261021, preset="demo-1021",
              home=team("home", "Harbour City", "HBC"), away=team("away", "Rovers", "ROV"),
              status="scheduled")
    data = m.model_dump(mode="json")
    assert data["score"] == {"home": 0, "away": 0}
    validate("Match", data)


def test_committed_schema_is_up_to_date():
    spec = importlib.util.spec_from_file_location("export_contracts", ROOT / "scripts/export_contracts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = (ROOT / "packages/contracts/schema/pivot.schema.json").read_text(encoding="utf-8")
    assert committed == module.build(), "run: uv run scripts/export_contracts.py"
