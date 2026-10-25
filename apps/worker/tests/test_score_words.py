"""Dx8: words about the score must fit the real score (#149)."""

import pytest

from pivot_core.domain import ExplanationSentence, Narrative, ViewerPrefs
from pivot_worker.testing import FakeStats, event
from pivot_worker.verifier import verify

TEAMS = {"home": "Harbour City", "away": "Northgate Rovers"}
PIVOT = 64


def m505():
    """M-seed-505 around its 64' pivot: Harbour City 2-0 up, Rovers pull one back, Harbour make it 3-1."""
    evs = [
        event("m064-s00112", 6, "shot", shot_outcome="goal", xg=0.3),
        event("m064-s00297", 16, "shot", shot_outcome="goal", xg=0.2),
        event("m064-s01240", 58, "substitution"),
        event("m064-s01389", 65, "shot", team="away", shot_outcome="goal", xg=0.4),
        event("m064-s01408", 67, "shot", shot_outcome="goal", xg=0.5),
        event("m064-s01435", 69, "shot", shot_outcome="saved", xg=0.1),
    ]
    return {e.event_id: e for e in evs}


def card(headline, text="Harbour City kept pushing after the substitution.", evidence=("m064-s01408",),
         lang="en"):
    sentence = ExplanationSentence(text=text, evidence_ids=list(evidence))
    return Narrative(prefs=ViewerPrefs(language=lang), headline=headline, sentences=[sentence], source="llm")


def problems(narrative, events=None, minute=PIVOT):
    verdict = verify(narrative, pivot_minute=minute, events=events or m505(), stats=FakeStats({}), team_names=TEAMS)
    return [i.message for i in verdict.issues]


def test_m505_equaliser_at_2_1_up_is_rejected():
    found = problems(card("Harbour City responds with swift equalizer"))
    assert len(found) == 1
    assert "'equalizer' does not fit the score" in found[0]
    assert "made it Harbour City 3-1 Northgate Rovers (it was Harbour City 2-1 Northgate Rovers)" in found[0]


def test_m505_extend_the_lead_passes():
    assert problems(card("Harbour City extend the lead at once")) == []
    assert problems(card("Harbour City strike back", "Harbour City extended their lead within two minutes.")) == []


@pytest.mark.parametrize("text", [
    "Northgate Rovers pulled level at 65'.",
    "Harbour City took the lead again at 67'.",
    "Harbour City completed a comeback at 67'.",
    "Harbour City were trailing before the substitution.",
])
def test_m505_wrong_score_stories_are_rejected(text):
    found = problems(card("Harbour City answer at once", text, evidence=("m064-s01389", "m064-s01408")))
    assert len(found) == 1 and "does not fit the score" in found[0]


@pytest.mark.parametrize("text", [
    "Northgate Rovers pulled one back at 65', so Harbour City were protecting their lead.",
    "Northgate Rovers were trailing, but kept chasing an equaliser.",
    "Harbour City sat on their lead and it nearly cost them.",
])
def test_m505_true_score_stories_pass(text):
    assert problems(card("Harbour City answer at once", text, evidence=("m064-s01389", "m064-s01408"))) == []


def test_a_real_equaliser_and_take_the_lead_pass():
    evs = {e.event_id: e for e in [
        event("m030-s00500", 30, "shot", team="away", shot_outcome="goal"),
        event("m030-s00900", 61, "shot", shot_outcome="goal"),
        event("m030-s01000", 66, "shot", shot_outcome="goal"),
    ]}
    assert problems(card("Harbour City draw level", evidence=("m030-s00900",)), evs) == []
    assert problems(card("Harbour City go ahead", evidence=("m030-s01000",)), evs) == []
    assert problems(card("A comeback for Harbour City", evidence=("m030-s01000",)), evs) == []
    assert problems(card("Harbour City go ahead", evidence=("m030-s00900",)), evs)   # that one only levelled it


def test_a_goal_word_with_no_goal_in_the_window():
    evs = {e.event_id: e for e in [event("m063-s01042", 61, "substitution")]}
    found = problems(card("The equaliser comes from the bench", evidence=("m063-s01042",)), evs)
    assert found == ["Headline: 'equaliser' describes a goal, but there is no goal from 57' to 70'."]


def test_the_conceding_side_named_still_finds_the_scorer():
    evs = {e.event_id: e for e in [event("m030-s00500", 30, "shot", team="away", shot_outcome="goal"),
                                   event("m030-s00900", 61, "shot", shot_outcome="goal")]}
    assert problems(card("Northgate Rovers concede the equaliser", evidence=("m030-s00900",)), evs) == []


@pytest.mark.parametrize("text", ["the pressing level changed", "Harbour City got in behind", "leading to more shots",
                                  "Harbour City fought back into midfield"])
def test_words_that_also_mean_other_things_are_not_score_words(text):
    assert problems(card("Harbour City change shape", f"After the substitution {text}.")) == []


@pytest.mark.parametrize(("lang", "headline", "ok"), [
    ("zh", "Harbour City 扳平比分", False),
    ("zh", "Harbour City 扩大领先", True),
    ("es", "Harbour City logró el empate", False),
    ("es", "Harbour City amplía la ventaja", True),
])
def test_chinese_and_spanish_score_words(lang, headline, ok):
    assert (problems(card(headline, "Harbour City 换人之后继续压上。" if lang == "zh" else
                          "Harbour City siguió presionando tras el cambio.", lang=lang)) == []) is ok


def test_what_if_comparisons_are_not_checked():
    narrative = card("A draw became less likely", "In the replays a draw became less likely than an equaliser.")
    verdict = verify(narrative, pivot_minute=PIVOT, events=m505(), stats=FakeStats({}), team_names=TEAMS,
                     significant={"draw": False}, outcomes=lambda text: [], allowed_evidence={"m064-s01408"})
    assert not any("score" in i.message for i in verdict.issues)
