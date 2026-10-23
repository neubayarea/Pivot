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
    StatMetric,
    StatRef,
    Team,
    ViewerPrefs,
)

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "packages/contracts/schema/pivot.schema.json").read_text(encoding="utf-8"))


def validate(name: str, data: dict) -> None:
    """Validate serialized output against one definition of the exported schema."""
    jsonschema.validate(data, {**SCHEMA, "$ref": f"#/$defs/{name}"})


def team(side: str, name: str, short: str) -> Team:
    prefix = side[0]
    return Team(
        side=side, name=name, short_name=short, color="#1E6B45",
        players=[Player(player_id=f"{prefix}{n}", name=f"Player {n}", team=side,
                        shirt_number=n, position="MF") for n in (7, 9)],
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


def test_stat_vocabulary_has_15_metrics_each_with_a_unit():
    metrics = typing.get_args(StatMetric)
    assert len(metrics) == 15
    assert set(STAT_UNITS) == set(metrics)


def test_event_minute_is_derived_from_the_clock():
    e = MatchEvent(match_id="M", seq=1042, event_id="m062-s01042", t=3750, period=2,
                   type="pass", team="home", from_zone=(7, 3), to_zone=(10, 4), outcome="success")
    assert e.minute == 62
    assert e.model_dump()["minute"] == 62
    validate("MatchEvent", e.model_dump(mode="json"))


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
