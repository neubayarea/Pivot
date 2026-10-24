from pivot_core.domain import Pivot, Substitution, TeamTactics
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
