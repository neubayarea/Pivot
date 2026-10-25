import json
from pathlib import Path

import pytest

from pivot_core.domain import FoulDetail, MatchEvent, Pivot, Substitution, TeamTactics
from pivot_worker import scenarios as sc
from pivot_worker.testing import event


def pivot(minute=62, triggers=("m063-s02302",), direction="away"):
    return Pivot(pivot_id=f"M-test:p{minute}", match_id="M-test", minute=minute, direction=direction, severity=3,
                 status="confirmed", trigger_event_ids=list(triggers), chain_id="c1")


SUB = Substitution(player_off_id="hcy-11", player_on_id="hcy-6", slot=11, reason="tactical")
DEMO = [
    event("m063-s00300", 11, "shot", shot_outcome="goal"),
    event("m063-s01500", 37, "card", team="away", meta={"card": "red"}),
    event("m063-s01510", 39, "card", team="home", meta={"card": "yellow"}),
    event("m063-s02302", 62, "substitution", substitution=SUB),
    event("m063-s02900", 70, "shot", team="away", shot_outcome="goal"),
]


def by_type(options):
    return {o.type: o for o in options}


def test_catalog_has_the_five_b5_scenarios_with_copy_and_conditions():
    assert list(sc.CATALOG) == ["cancel_substitution", "remove_red_card", "move_substitution", "remove_goal",
                                "change_press"]
    for entry in sc.CATALOG.values():
        assert entry.label and entry.description and entry.applies_when and entry.resume_from and entry.params


def test_options_for_the_demo_substitution_pivot():
    options = sc.options_for(pivot(), DEMO)
    assert options[0].type == "cancel_substitution"          # the pivot's own trigger comes first
    o = by_type(options)
    assert o["cancel_substitution"].label == "Cancel 63′ substitution"
    assert o["cancel_substitution"].at_minute == 62 and o["cancel_substitution"].team == "home"
    assert o["remove_red_card"].label == "Remove 38′ red card" and o["remove_red_card"].enabled
    assert o["move_substitution"].label == "Move substitution to 75′"
    assert o["move_substitution"].params == {"new_minute": 74} and o["move_substitution"].at_minute == 62
    assert o["remove_goal"].label == "Disallow 71′ goal"      # the goal nearest the pivot
    assert o["change_press"].label == "Press higher from 63′" and o["change_press"].team == "home"


def test_unavailable_scenarios_are_disabled_with_a_reason():
    o = by_type(sc.options_for(pivot(minute=20, triggers=()), DEMO[:1]))
    assert not o["remove_red_card"].enabled
    assert o["remove_red_card"].label == "Remove red card"
    assert o["remove_red_card"].disabled_reason == "No red card in this match"
    assert not o["cancel_substitution"].enabled and o["remove_goal"].enabled


def test_yellow_cards_and_shootout_goals_do_not_count():
    assert not sc.is_red_card(DEMO[2])
    assert sc.is_red_card(event("m063-s00001", 30, "card", meta={"card": "second_yellow"}))
    kick = DEMO[0].model_copy(update={"period": 5})
    assert not sc.is_goal(kick)


def test_red_cards_are_read_from_the_foul():
    foul = FoulDetail(foul_type="tackle", card="red", card_reason="professional_foul")
    red = event("m063-s00002", 30, "card", foul=foul)
    second = red.model_copy(update={"foul": foul.model_copy(update={"card": "second_yellow"})})
    yellow = red.model_copy(update={"foul": foul.model_copy(update={"card": "yellow"})})
    assert sc.is_red_card(red) and sc.is_red_card(second) and not sc.is_red_card(yellow)


def test_target_prefers_a_trigger_then_the_lead_up_then_a_tactical_substitution():
    fatigue = SUB.model_copy(update={"reason": "fatigue"})
    events = [event("m063-s00100", 50, "substitution", substitution=fatigue),
              event("m063-s00200", 52, "substitution", substitution=SUB),
              event("m063-s00300", 58, "substitution", substitution=fatigue),
              event("m063-s00400", 66, "substitution", substitution=fatigue)]

    def target(minute, triggers=()):
        return by_type(sc.options_for(pivot(minute=minute, triggers=triggers), events))["cancel_substitution"].at_minute

    assert target(64, ["m063-s00100"]) == 50        # the pivot's own trigger
    assert target(64) == 52                         # in the lead-up, tactical over the nearer 58' one
    assert target(80) == 66                         # nothing in the 15' before: the nearest
    assert target(20) == 52                         # all after the pivot: still the tactical one
    goals = [event("m063-s00500", 30, "shot", shot_outcome="goal"), event("m063-s00600", 41, "shot", shot_outcome="goal")]
    assert by_type(sc.options_for(pivot(minute=38, triggers=()), goals))["remove_goal"].at_minute == 30


# --- the recorded demo (eval/fixtures/demo-1021.json, M-seed-41) ----------------------------

FIXTURE = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "demo-1021.json"


@pytest.fixture(scope="module")
def demo():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    events = [MatchEvent.model_validate(e) for e in data["events"]]
    candidates = {c["minute"]: c for c in data["candidates"]}

    def at(minute, triggers=True):
        c = candidates[minute]
        return by_type(sc.options_for(Pivot(
            pivot_id=f"M-seed-41:p{minute}", match_id="M-seed-41", minute=minute, direction=c["direction"],
            severity=3, status="confirmed", trigger_event_ids=c["key_event_ids"] if triggers else [],
            chain_id="c1"), events))
    return {e.event_id: e for e in events}, at


def test_demo_39_offers_removing_the_planted_red_card(demo):
    events, at = demo
    for o in (at(39), at(39, triggers=False)):
        red = o["remove_red_card"]
        assert red.enabled and red.label == "Remove 38′ red card"
        assert events[red.target_event_id].foul.card == "red" and red.at_minute == 37 and red.team == "away"


@pytest.mark.parametrize("triggers", [True, False])
def test_demo_69_substitution_chips_target_the_planted_tactical_change(demo, triggers):
    events, at = demo
    o = at(69, triggers)
    for type_ in ("cancel_substitution", "move_substitution"):
        sub = events[o[type_].target_event_id]
        assert sub.minute == 66 and sub.substitution.reason == "tactical"   # 63' on the clock
        assert (sub.substitution.player_off_id, sub.substitution.player_on_id) == ("h09", "h15")
    assert o["cancel_substitution"].label == "Cancel 67′ substitution"


def test_move_minute_range():
    assert sc.move_minute_valid(45) and sc.move_minute_valid(84)
    assert not sc.move_minute_valid(44) and not sc.move_minute_valid(85)


def test_list_scenario_types_for_the_translator():
    tools = sc.list_scenario_types()
    assert [t["type"] for t in tools] == list(sc.CATALOG)
    assert tools[2]["params"] == ["target_event_id", "new_minute"]


def test_change_press_becomes_a_spec_with_tactics():
    press = by_type(sc.options_for(pivot(), DEMO))["change_press"]
    spec = press.to_spec("M-test:p62", seed_base=7)
    assert spec.type == "change_press" and spec.team == "home" and spec.at_minute == 62
    assert spec.tactics == TeamTactics(press="high") and "delta" not in spec.params
    high = by_type(sc.options_for(pivot(), DEMO, tactics={"home": TeamTactics(press="high", width="wide")}))
    assert high["change_press"].label == "Press lower from 63′"
    assert high["change_press"].to_spec("M-test:p62", seed_base=7).tactics == TeamTactics(press="mid", width="wide")


def test_other_options_become_specs_too():
    move = by_type(sc.options_for(pivot(), DEMO))["move_substitution"].to_spec("M-test:p62", seed_base=1, n_runs=200)
    assert move.target_event_id == "m063-s02302" and move.params == {"new_minute": 74} and move.n_runs == 200
