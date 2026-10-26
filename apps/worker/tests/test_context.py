import json
from pathlib import Path

from pivot_core.domain import (
    CareerStint,
    Coach,
    ContextEffect,
    ExplanationSentence,
    Match,
    MatchContext,
    Narrative,
    OffFieldEvent,
    PivotCandidate,
    Player,
    Relationship,
    Substitution,
    Team,
    ViewerPrefs,
)
from pivot_core.domain.context import Competition
from pivot_worker import context as ctx
from pivot_worker import explainer as ex
from pivot_worker.template import context_text as ctx_text
from pivot_worker.template import template_explain
from pivot_worker.testing import event
from pivot_worker.verifier import verify

TEAMS = {"home": "Rovers", "away": "Harbour"}
STINT = CareerStint(stint_id="h09-c1", club_id="club-hbr", club_name="Harbour", from_year=2019, to_year=2023,
                    departure="transfer", departure_mood="acrimonious")
CONTEXT = MatchContext(
    competition=Competition(competition_id="c1", name="Continental Club Cup", level="continental_club", importance=4),
    venue="Rovers Park",
    news=[OffFieldEvent(news_id="n1", subject_id="a04", kind="nightlife", hours_before_kickoff=20, sentiment="negative",
                        headline="Harbour defender seen out late"),
          OffFieldEvent(news_id="n2", subject_id="a05", kind="illness", hours_before_kickoff=5, sentiment="negative",
                        public=False, headline="Private illness")],
    relationships=[Relationship(relationship_id="r1", person_id="h09", other_id="a-coach", kind="feud")],
    effects=[ContextEffect(effect_id="e1", subject_id="h09", source="former_club", source_ref="h09-c1",
                           target="motivation", delta=0.1, note="first game back at the club that sold him")],
)
NAMES = {"h09": "R. Okafor", "a04": "T. Brandt", "a-coach": "L. Varga"}
SUB = Substitution(player_off_id="h11", player_on_id="h09", slot=11, reason="tactical")


def items():
    return ctx.context_items(CONTEXT, names=NAMES, reunions=[("h09", STINT)])


def candidate():
    return PivotCandidate(match_id="M-test", minute=63, direction="home", cusum_stat=4.2, swing=0.3,
                          key_event_ids=["m063-s01042"], window=(58, 68))


def sub_events(events):
    return {**events, "m063-s01042": event("m063-s01042", 61, "substitution", substitution=SUB)}


def test_context_items_cover_effects_public_news_relationships_and_reunions():
    by_id = {i.context_id: i for i in items()}
    assert set(by_id) == {"e1", "n1", "r1", "h09-c1"}                       # n2 is not public
    assert by_id["e1"].text == "R. Okafor: first game back at the club that sold him"
    assert by_id["r1"].text == "R. Okafor and L. Varga: feud"
    assert by_id["h09-c1"].text == "R. Okafor played for Harbour before"


def test_effects_without_a_story_come_after_the_stories():
    crowd = ContextEffect(effect_id="e2", subject_id="a04", source="crowd", target="composure", delta=-0.01,
                          note="away crowd")
    form = ContextEffect(effect_id="e3", subject_id="h09", source="form", target="motivation", delta=0.02,
                         note="good form")
    more = CONTEXT.model_copy(update={"effects": [crowd, form, *CONTEXT.effects]})
    order = [i.context_id for i in ctx.context_items(more, names=NAMES, reunions=[("h09", STINT)])]
    assert order == ["e1", "n1", "r1", "h09-c1", "e2", "e3"]


def test_from_match_finds_reunions_with_the_opponent():
    def player(pid, side, career=()):
        return Player.model_construct(player_id=pid, name=NAMES.get(pid, pid), team=side, career=list(career))

    def team(side, club, squad):
        coach = Coach.model_construct(coach_id=f"{side[0]}-coach", name="Coach", career=[])
        return Team.model_construct(side=side, club_id=club, name=club, squad=squad, coach=coach)

    match = Match.model_construct(home=team("home", "club-rov", [player("h09", "home", [STINT])]),
                                  away=team("away", "club-hbr", [player("a04", "away")]), context=CONTEXT)
    assert "h09-c1" in ctx.known_ids(ctx.from_match(match))


def test_relevant_puts_people_in_the_window_first(events):
    ranked = ctx.relevant(items(), sub_events(events).values(), limit=2)
    assert {i.context_id for i in ranked} <= {"e1", "r1", "h09-c1"}


def test_explainer_request_lists_the_context(events, stats):
    prompt, messages = ex.build_messages(candidate(), events=sub_events(events), stats=stats, team_names=TEAMS,
                                         context=items())
    listed = json.loads(messages[1]["content"])["match_context"]
    assert listed[0]["about"] == ["h09"] and "never invent an id" in prompt.text


def card(context_ids):
    return Narrative(prefs=ViewerPrefs(), headline="Okafor returns to hurt Harbour", source="llm", sentences=[
        ExplanationSentence(text="Okafor, back against the club that sold him, came on and changed the game.",
                            evidence_ids=["m063-s01042"], context_ids=context_ids)])


def test_real_context_passes_and_invented_context_is_caught(events, stats):
    assert verify(card(["e1", "h09-c1"]), pivot_minute=63, events=events, stats=stats, context=items()).passed
    verdict = verify(card(["e9"]), pivot_minute=63, events=events, stats=stats, context=items())
    assert [i.code for i in verdict.issues] == ["context_invalid"]
    assert [i.code for i in verify(card(["e1"]), pivot_minute=63, events=events, stats=stats).issues] == [
        "context_invalid"]


def test_template_cites_context_about_the_trigger_player(events, stats):
    evs = sub_events(events)
    narrative = template_explain(candidate(), events=evs, stats=stats, team_names=TEAMS, context=items())
    cited = [s for s in narrative.sentences if s.context_ids]
    # The reunion, as a sentence: effects ("first game back ...") are notes for the simulator (#219).
    assert cited and cited[0].context_ids == ["h09-c1"] and len(narrative.sentences) == 3
    assert cited[0].text == "R. Okafor played for Harbour before."
    assert verify(narrative, pivot_minute=63, events=evs, stats=stats, context=items()).passed


def test_template_writes_each_kind_of_context_as_a_whole_sentence():
    # Not "R. Okafor and L. Varga: feud" or "Off the pitch: X and Y: former teammate" (#219).
    by_id = {i.context_id: i for i in items()}
    assert ctx_text(by_id["r1"], {"h09"}) == "R. Okafor and L. Varga do not get on."
    assert ctx_text(by_id["r1"], {"a-coach"}) == "L. Varga and R. Okafor do not get on."   # the one in the event first
    assert ctx_text(by_id["n1"], {"a04"}) == "In the news before the match: Harbour defender seen out late."
    assert ctx_text(by_id["h09-c1"], {"h09"}) == "R. Okafor played for Harbour before."
    assert ctx_text(by_id["e1"], {"h09"}) is None
    mates = ctx.ContextItem("r2", "relationship", ("a04", "h09"), "T. Brandt and R. Okafor: former teammate",
                            ("T. Brandt", "R. Okafor"), "former_teammate")
    assert ctx_text(mates, {"h09"}) == "R. Okafor and T. Brandt used to be teammates."


def test_demo_fixture_gives_the_writers_off_field_stories():
    path = Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "demo-1021.json"
    match = Match.model_validate(json.loads(path.read_text(encoding="utf-8"))["match"])
    items = ctx.from_match(match)
    kinds = {i.kind for i in items}
    assert {"former_club", "news", "relationship"} <= kinds
    assert {"a04-c1", "h13-c2", "news-a04-return", "news-h15-100"} <= ctx.known_ids(items)
