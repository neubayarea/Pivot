import importlib.util
import json
import typing
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from pivot_core.domain import (
    STAT_UNITS,
    CareerStint,
    Claim,
    Coach,
    Competition,
    ContextEffect,
    ExplanationSentence,
    LineupSlot,
    Match,
    MatchContext,
    MatchEvent,
    Narrative,
    OffFieldEvent,
    Personality,
    Pivot,
    Player,
    PlayerAttributes,
    Relationship,
    StatMetric,
    StatRef,
    Team,
    TeamSheet,
    TeamTactics,
    TrackingFrame,
    ViewerPrefs,
    area_of,
    lane_of,
    third_of,
    zone_of,
)

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "packages/contracts/schema/pivot.schema.json").read_text(encoding="utf-8"))


def validate(name: str, data: dict) -> None:
    """Validate serialized output against one definition of the exported schema."""
    jsonschema.validate(data, {**SCHEMA, "$ref": f"#/$defs/{name}"})


def attributes(base: int = 70) -> PlayerAttributes:
    def group(*names: str) -> dict:
        return {n: base for n in names}
    return PlayerAttributes(
        attacking=group("crossing", "finishing", "heading_accuracy", "short_passing", "volleys"),
        skill=group("dribbling", "curve", "free_kick_accuracy", "long_passing", "ball_control"),
        movement=group("acceleration", "sprint_speed", "agility", "reactions", "balance"),
        power=group("shot_power", "jumping", "stamina", "strength", "long_shots"),
        mentality=group("aggression", "interceptions", "attack_positioning", "vision", "penalties",
                        "composure"),
        defending=group("defensive_awareness", "standing_tackle", "sliding_tackle"),
        goalkeeping=group("diving", "handling", "kicking", "positioning", "reflexes"),
    )


PERSONALITY = Personality(**{f: 60 for f in Personality.model_fields})

ROLES_433 = ["GK", "RB", "CB", "CB", "LB", "DM", "CM", "CM", "RW", "ST", "LW"]
ANCHORS_433 = [(4, 34), (30, 8), (25, 25), (25, 43), (30, 60), (40, 34), (50, 22), (50, 46),
               (72, 10), (78, 34), (72, 58)]


def player(side: str, n: int, role: str, **extra) -> Player:
    return Player(player_id=f"{side[0]}{n:02d}", name=f"Player {n}", team=side, shirt_number=n,
                  role=role, age=26, nationality="Freeland", height_cm=180, weight_kg=75,
                  attributes=attributes(), personality=PERSONALITY, **extra)


def team(side: str, name: str, short: str) -> Team:
    squad = [player(side, n, role) for n, role in enumerate(ROLES_433, start=1)]
    squad += [player(side, 12 + i, role) for i, role in enumerate(["GK", "CB", "CM", "ST"])]
    pid = [p.player_id for p in squad]
    sheet = TeamSheet(
        formation="4-3-3",
        starters=[LineupSlot(player_id=pid[i], slot=i + 1, role=r, anchor=ANCHORS_433[i])
                  for i, r in enumerate(ROLES_433)],
        bench=pid[11:], captain_id=pid[5], penalty_taker_id=pid[9], free_kick_taker_id=pid[6],
        corner_taker_left_id=pid[8], corner_taker_right_id=pid[10],
    )
    coach = Coach(coach_id=f"{side[0]}-coach", name="A. Moreau", age=51, nationality="Freeland",
                  style="balanced", preferred_formation="4-3-3",
                  attributes={"tactical_knowledge": 75, "in_game_adaptability": 70,
                              "man_management": 68, "motivation": 72},
                  personality=PERSONALITY)
    return Team(side=side, club_id=f"club-{short.lower()}", name=name, short_name=short,
                color="#1E6B45", coach=coach, squad=squad, sheet=sheet, tactics=TeamTactics())


def context() -> MatchContext:
    return MatchContext(
        competition=Competition(competition_id="cl-1", name="Continental Club Cup",
                                level="continental_club", stage="quarter_final", importance=4),
        venue="Harbour Park", attendance=41250, stakes="knockout", weather="rain",
        news=[OffFieldEvent(news_id="n1", subject_id="a09", kind="nightlife", hours_before_kickoff=20,
                            severity=2, sentiment="negative",
                            headline="Rovers striker seen at a late-night club two nights before the tie")],
        relationships=[Relationship(relationship_id="r1", person_id="a09", other_id="h-coach",
                                    kind="former_coach", shared_seasons=3, sentiment=-0.6)],
        effects=[ContextEffect(effect_id="e1", subject_id="a09", source="off_field", source_ref="n1",
                               target="fitness", delta=-0.05, note="late night before the match")],
    )


def sentence(text: str, value: float, **extra) -> ExplanationSentence:
    return ExplanationSentence(
        text=text, evidence_ids=["m061-s01012", "m063-s01042"],
        claims=[Claim(value=value, unit="count",
                      stat_ref=StatRef(metric="shots", team="away", window=(63, 68)))],
        **extra,
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


# --- stats -----------------------------------------------------------------------------

def test_stat_vocabulary_has_19_metrics_each_with_a_unit():
    metrics = typing.get_args(StatMetric)
    assert len(metrics) == 19
    assert set(STAT_UNITS) == set(metrics)


# --- people ----------------------------------------------------------------------------

def test_34_ratings_in_seven_groups():
    groups = PlayerAttributes.model_fields
    assert len(groups) == 7
    assert sum(len(groups[g].annotation.model_fields) for g in groups) == 34


def test_summary_ratings_are_weighted_from_the_detail():
    a = attributes(80)
    assert a.summary.model_dump() == {k: 80 for k in
                                      ("pace", "shooting", "passing", "dribbling", "defending", "physical")}
    fast = a.model_copy(update={"movement": a.movement.model_copy(update={"sprint_speed": 99})})
    assert fast.summary.pace == round(0.45 * 80 + 0.55 * 99)


def test_ratings_stay_between_1_and_99():
    with pytest.raises(ValidationError):
        PlayerAttributes.model_validate({**attributes().model_dump(exclude={"summary"}),
                                         "movement": {**attributes().movement.model_dump(), "acceleration": 120}})


def test_player_position_group_follows_the_role_and_career_validates():
    p = player("home", 7, "RW", career=[
        CareerStint(stint_id="h07-c1", club_id="club-rov", club_name="Rovers", from_year=2019,
                    to_year=2023, appearances=118, goals=31, departure="transfer",
                    departure_mood="acrimonious"),
        CareerStint(stint_id="h07-c2", club_id="club-hbc", club_name="Harbour City", from_year=2023),
    ])
    data = p.model_dump(mode="json")
    assert data["position"] == "FW"
    validate("Player", data)


# --- lineup ----------------------------------------------------------------------------

def test_team_sheet_allows_seven_to_eleven_starters():
    sheet = team("home", "Harbour City", "HBC").sheet
    validate("TeamSheet", sheet.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        TeamSheet.model_validate({**sheet.model_dump(), "starters": sheet.model_dump()["starters"][:6]})


def test_tactical_shift_event_carries_the_new_sheet_and_tactics():
    t = team("away", "Rovers", "ROV")
    e = MatchEvent(match_id="M", seq=2001, event_id="m063-s02001", t=3780, period=2,
                   type="tactical_shift", team="away", team_sheet=t.sheet.model_copy(update={"formation": "5-4-1"}),
                   tactics=TeamTactics(line_height="low", press="low", counter_attack=True))
    validate("MatchEvent", e.model_dump(mode="json"))


# --- match -----------------------------------------------------------------------------

def test_full_match_with_context_matches_the_schema():
    m = Match(match_id="M-seed-20261021", seed=20261021, preset="demo-1021",
              home=team("home", "Harbour City", "HBC"), away=team("away", "Rovers", "ROV"),
              context=context(), status="scheduled")
    data = m.model_dump(mode="json")
    assert data["score"] == {"home": 0, "away": 0}
    validate("Match", data)


def test_context_effects_stay_small():
    with pytest.raises(ValidationError):
        ContextEffect(effect_id="e", subject_id="a09", source="former_club", target="motivation",
                      delta=0.4, note="too big")


# --- events and pitch geometry ---------------------------------------------------------

def test_event_minute_zones_and_tactical_areas_are_derived():
    e = MatchEvent(match_id="M", seq=1042, event_id="m062-s01042", t=3750, period=2,
                   type="pass", team="home", player_id="h07", receiver_id="h09",
                   location=(64.2, 30.1), end_location=(88.0, 34.5), outcome="success",
                   ball_speed_kmh=52.0, under_pressure=True, possession_id=118,
                   play_pattern="counter")
    data = e.model_dump(mode="json")
    assert (data["minute"], data["from_zone"], data["to_zone"]) == (62, [9, 5], [13, 6])
    assert (data["third"], data["lane"], data["area"]) == ("middle", "centre", "open")
    validate("MatchEvent", data)


def test_grid_is_16_by_12_and_clamps_at_the_edges():
    assert zone_of((0.0, 0.0)) == (0, 0)
    assert zone_of((105.0, 68.0)) == (15, 11)


def test_areas_are_seen_from_the_attacking_side():
    # The same spot near the x = 105 goal is the opponent's six-yard box for home, its own for away.
    assert area_of((102.0, 34.0), "home") == "opp_six_yard_box"
    assert area_of((102.0, 34.0), "away") == "own_six_yard_box"
    assert area_of((92.0, 20.0), "home") == "opp_box"
    assert third_of((80.0, 34.0), "home") == "final" and third_of((80.0, 34.0), "away") == "defensive"
    # Facing x = 105, the home team's left is the high-y touchline; for away it is the low-y one.
    assert lane_of((50.0, 62.0), "home") == "left_wing"
    assert lane_of((50.0, 62.0), "away") == "right_wing"
    assert lane_of((50.0, 20.0), "home") == "right_half_space"


def test_a_goal_is_a_shot_with_outcome_goal():
    e = MatchEvent(match_id="M", seq=7, event_id="m038-s00007", t=2290, period=1, type="shot",
                   team="away", player_id="a09", location=(14.0, 33.0), end_location=(0.0, 34.2),
                   shot_outcome="goal", xg=0.31, ball_speed_kmh=96.5, shot_end_height_m=1.9)
    validate("MatchEvent", e.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        MatchEvent(match_id="M", seq=8, event_id="x", t=1, period=1, type="goal", team="home")


def test_pass_carries_difficulty_type_height_and_links():
    e = MatchEvent(match_id="M", seq=1041, event_id="m062-s01041", t=3749, period=2, type="pass",
                   team="home", player_id="h06", receiver_id="h09", location=(48.0, 34.0),
                   end_location=(86.0, 30.0), outcome="success", success_prob=0.38,
                   pass_type="through_ball", pass_height="ground", body_part="right_foot",
                   ball_speed_kmh=61.0, related_event_ids=["m062-s01042"])
    validate("MatchEvent", e.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        MatchEvent.model_validate({**e.model_dump(exclude={"minute", "from_zone", "to_zone", "third",
                                                           "lane", "area"}), "success_prob": 1.2})


def test_tracking_frame_holds_at_most_22_players_inside_the_pitch():
    frame = TrackingFrame(
        match_id="M", t=3750, period=2, possession="home",
        ball={"x": 64.2, "y": 30.1, "owner_id": "h07"},
        players=[{"player_id": f"h{n}", "x": 50.0 + n, "y": 30.0, "speed_ms": 4.2, "fitness": 0.8}
                 for n in range(1, 12)],
    )
    validate("TrackingFrame", frame.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        TrackingFrame(match_id="M", t=1, period=1, possession=None, ball={"x": 106.0, "y": 0.0}, players=[])
    with pytest.raises(ValidationError):
        TrackingFrame(match_id="M", t=1, period=1, possession=None, ball={"x": 52.5, "y": 34.0},
                      players=[{"player_id": f"p{n}", "x": 1.0, "y": 1.0} for n in range(23)])


# --- narratives ------------------------------------------------------------------------

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


def test_sentence_can_cite_off_pitch_context():
    s = sentence("Facing the coach who sold him, Okafor took 4 shots.", 4, context_ids=["r1", "e1"])
    validate("ExplanationSentence", s.model_dump(mode="json"))


# --- contracts -------------------------------------------------------------------------

def test_committed_schema_is_up_to_date():
    spec = importlib.util.spec_from_file_location("export_contracts", ROOT / "scripts/export_contracts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = (ROOT / "packages/contracts/schema/pivot.schema.json").read_text(encoding="utf-8")
    assert committed == module.build(), "run: uv run scripts/export_contracts.py"
