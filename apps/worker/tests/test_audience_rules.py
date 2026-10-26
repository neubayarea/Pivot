"""Counter-examples for #104: fan-version and off-pitch rules the Verifier must enforce, not just the prompt."""

import asyncio
import json

import pytest

from pivot_adapters import build_adapters
from pivot_core.domain import (
    Coach,
    ContextEffect,
    ExplanationSentence,
    Match,
    MatchContext,
    Narrative,
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
from pivot_worker.detect import DetectWorkflow
from pivot_worker.models import ScriptedModelClient
from pivot_worker.template import template_explain
from pivot_worker.testing import FakeStats, claim, event
from pivot_worker.verifier import numbers_in, verify

TEAMS = {"home": "Rovers", "away": "Harbour"}
FAN = ViewerPrefs(audience="fan")
EFFECT = ContextEffect(effect_id="e1", subject_id="h09", source="former_club", source_ref="h09-c1",
                       target="motivation", delta=0.1, note="first game back at the club that sold him")
FEUD = Relationship(relationship_id="r1", person_id="a04", other_id="a-coach", kind="feud")
CONTEXT = MatchContext(
    competition=Competition(competition_id="c1", name="Continental Club Cup", level="continental_club", importance=4),
    venue="Rovers Park", effects=[EFFECT], relationships=[FEUD])
NAMES = {"h09": "R. Okafor", "a04": "T. Brandt", "a-coach": "L. Varga"}
SUB = Substitution(player_off_id="h11", player_on_id="h09", slot=11, reason="tactical")


def candidate(direction="home"):
    return PivotCandidate(match_id="M-test", minute=63, direction=direction, cusum_stat=4.2, swing=0.3,
                          key_event_ids=["m063-s01042"], window=(58, 68))


def card(text, prefs=ViewerPrefs(), claims=(), context_ids=(), headline=None):
    headline = headline or ("Rovers接管比赛" if prefs.language == "zh" else "Rovers take over")
    return Narrative(prefs=prefs, headline=headline, source="llm", sentences=[ExplanationSentence(
        text=text, evidence_ids=["m063-s01042"], claims=list(claims), context_ids=list(context_ids))])


def codes(verdict):
    return [i.code for i in verdict.issues]


PFT = [claim("passes_final_third", "home", (56, 61), 3), claim("passes_final_third", "home", (61, 66), 9)]


# 1. Fan versions: at most one number per sentence, and the examples and the template keep to it.

def test_fan_sentence_with_two_numbers_is_rejected(events, stats):
    text = "Rovers' passes into the attacking third rose from 3 to 9."
    assert verify(card(text, claims=PFT), pivot_minute=63, events=events, stats=stats).passed
    verdict = verify(card(text, FAN, PFT), pivot_minute=63, events=events, stats=stats)
    assert codes(verdict) == ["number_mismatch"] and "one number" in verdict.issues[0].message


def test_fan_sentence_with_one_number_and_a_direction_passes(events, stats):
    text = "Rovers' passes into the attacking third rose to 9."
    assert verify(card(text, FAN, PFT), pivot_minute=63, events=events, stats=stats).passed


def test_fan_example_follows_the_fan_rules():
    for s in ex.FAN_EXAMPLE.sentences:
        assert len(numbers_in(s.text)) <= 1, s.text


@pytest.mark.parametrize("lang", ["en", "zh", "es"])
def test_fan_template_sentences_have_at_most_one_number(events, stats, lang):
    prefs = ViewerPrefs(audience="fan", language=lang)
    narrative = template_explain(candidate(), events=events, stats=stats, team_names=TEAMS, prefs=prefs)
    assert any(s.claims for s in narrative.sentences)
    assert all(len(numbers_in(s.text, lang)) <= 1 for s in narrative.sentences)
    assert verify(narrative, pivot_minute=63, events=events, stats=stats).passed


# 2. Fan jargon is caught when spelled out and in every language.

@pytest.mark.parametrize("lang,text", [
    ("en", "Rovers' expected goals went up after the change."),
    ("en", "Their expected-goals total grew."),
    ("zh", "换人之后，流浪者的预期进球变多了。"),
    ("es", "Tras el cambio, los goles esperados de Rovers crecieron."),
])
def test_spelled_out_jargon_is_caught_in_fan_versions(events, stats, lang, text):
    analyst = verify(card(text, ViewerPrefs(language=lang)), pivot_minute=63, events=events, stats=stats)
    fan = verify(card(text, ViewerPrefs(audience="fan", language=lang)), pivot_minute=63, events=events, stats=stats)
    assert "banned_term" not in codes(analyst) and "banned_term" in codes(fan)


# 3. The template tells it from the focus team's side.

def test_template_follows_the_focus_team(events):
    stats = FakeStats({("threat_total", "away", (58, 63)): 0.44, ("threat_total", "away", (63, 68)): 0.12,
                       ("threat_total", "home", (58, 63)): 0.21, ("threat_total", "home", (63, 68)): 0.57})
    prefs = ViewerPrefs(focus_team="away")
    narrative = template_explain(candidate(), events=events, stats=stats, team_names=TEAMS, prefs=prefs)
    text = " ".join(s.text for s in narrative.sentences)
    assert "Harbour's threat created fell" in text and "towards Rovers" not in text and "Harbour" in text
    assert {c.stat_ref.team for s in narrative.sentences for c in s.claims} == {"away"}
    assert verify(narrative, pivot_minute=63, events=events, stats=stats).passed


# 4. A focus player seen only as a receiver or a substitute still gets player stats.

@pytest.mark.parametrize("extra", [
    event("m063-s01080", 62, receiver_id="rov-9"),
    event("m063-s01080", 61, "substitution",
          substitution=Substitution(player_off_id="rov-2", player_on_id="rov-9", slot=9, reason="tactical")),
])
def test_focus_player_as_receiver_or_substitute_gets_player_stats(events, stats, extra):
    evs = {**events, extra.event_id: extra}
    _, messages = ex.build_messages(candidate(), events=evs, stats=stats, team_names=TEAMS,
                                    prefs=ViewerPrefs(focus_player_id="rov-9"))
    sheet = json.loads(messages[1]["content"])["stat_sheet"]
    assert [c for c in sheet if c["stat_ref"]["player_id"] == "rov-9"]


# 5. An off-pitch story without a context id is caught.

def items():
    return ctx.context_items(CONTEXT, names=NAMES)


@pytest.mark.parametrize("lang,text", [
    ("en", "Okafor, back against his former club, changed the game."),
    ("en", "The feud with the Harbour coach fired Okafor up."),
    ("zh", "Okafor面对老东家，改变了比赛。"),
    ("es", "Okafor, ante su antiguo club, cambió el partido."),
])
def test_off_pitch_story_without_a_context_id_is_caught(events, stats, lang, text):
    verdict = verify(card(text, ViewerPrefs(language=lang)), pivot_minute=63, events=events, stats=stats,
                     context=items())
    assert codes(verdict) == ["context_invalid"]


def test_off_pitch_headline_needs_a_cited_item(events, stats):
    plain = "Okafor came on and changed the game."
    verdict = verify(card(plain, headline="Okafor haunts his old club"), pivot_minute=63, events=events,
                     stats=stats, context=items())
    assert codes(verdict) == ["context_invalid"]
    cited = card(plain, context_ids=["e1"], headline="Okafor haunts his old club")
    assert verify(cited, pivot_minute=63, events=events, stats=stats, context=items()).passed


# 6. A cited item must be about someone in the sentence, and one the writer was shown.

def test_context_about_someone_else_is_rejected(events, stats):
    text = "Okafor came on and changed the game."
    assert verify(card(text, context_ids=["e1"]), pivot_minute=63, events=events, stats=stats,
                  context=items()).passed
    verdict = verify(card(text, context_ids=["r1"]), pivot_minute=63, events=events, stats=stats, context=items())
    assert codes(verdict) == ["context_invalid"] and "T. Brandt" in verdict.issues[0].message


def test_context_counts_people_in_the_evidence(events, stats):
    evs = {**events, "m063-s01042": event("m063-s01042", 61, "substitution", substitution=SUB)}
    narrative = card("The substitute changed the game.", context_ids=["e1"])
    assert verify(narrative, pivot_minute=63, events=evs, stats=stats, context=items()).passed


def test_context_the_writer_was_not_shown_is_rejected(events, stats):
    crowd = [ctx.ContextItem(f"x{i}", "news", ("h09",), f"R. Okafor: story {i}", ("R. Okafor",)) for i in range(9)]
    shown = ex.shown_context(candidate(), events, crowd)
    assert len(shown) == ctx.MAX_ITEMS
    hidden = next(i.context_id for i in crowd if i not in shown)
    request = json.loads(ex.build_request(candidate(), events=events, stats=stats, team_names=TEAMS,
                                          context=crowd))
    assert [i["id"] for i in request["match_context"]] == [i.context_id for i in shown]
    narrative = card("Okafor came on and changed the game.", context_ids=[hidden])
    assert codes(verify(narrative, pivot_minute=63, events=events, stats=stats, context=shown)) == [
        "context_invalid"]


# 7. Production wiring: the workflow hands the match context to the writer and the Verifier.

def _match():
    def team(side, club, squad):
        coach = Coach.model_construct(coach_id=f"{side[0]}-coach", name="L. Varga", career=[])
        return Team.model_construct(side=side, club_id=club, name=TEAMS[side], squad=squad, coach=coach)

    okafor = Player.model_construct(player_id="h09", name="R. Okafor", team="home", career=[])
    brandt = Player.model_construct(player_id="a04", name="T. Brandt", team="away", career=[])
    return Match.model_construct(match_id="M-test", home=team("home", "club-rov", [okafor]),
                                 away=team("away", "club-hbr", [brandt]), context=CONTEXT)


def _workflow_run(events, stats, cited):
    adapters = build_adapters("local")
    evs = {**events, "m063-s01042": event("m063-s01042", 61, "substitution", substitution=SUB)}
    asyncio.run(adapters.matches.upsert_match(_match()))
    asyncio.run(adapters.matches.append_events(list(evs.values())))
    yes = json.dumps({"is_pivot": True, "severity": 2, "trigger_event_ids": ["m063-s01042"], "reason": "sub"})
    draft = json.dumps({"headline": "Okafor returns to hurt Harbour", "sentences": [{
        "text": "Okafor, back against the club that sold him, came on and changed the game.",
        "evidence_ids": ["m063-s01042"], "context_ids": [cited]}]})
    models = ScriptedModelClient(standard=[draft] * 3, mini=[yes])

    async def record(step):
        pass

    workflow = DetectWorkflow(adapters.matches, models, stats_factory=lambda m, e, x: stats)
    return asyncio.run(workflow.run(candidate(), "chain-1", record)), models


def test_workflow_passes_the_match_context_through(events, stats):
    pivot, models = _workflow_run(events, stats, "e1")
    request = json.loads(models.calls[1][1][1]["content"])
    assert "e1" in [i["id"] for i in request["match_context"]]
    assert pivot.status == "confirmed" and pivot.narrative.sentences[0].context_ids == ["e1"]


def test_workflow_rejects_context_about_someone_else(events, stats):
    pivot, _ = _workflow_run(events, stats, "r1")
    assert pivot.status == "degraded" and pivot.narrative.source == "template"
