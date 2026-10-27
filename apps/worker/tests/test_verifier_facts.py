"""The Verifier checks the facts a card states, not only its numbers (#186, #187, #208, #254).

The cases are the ones the issues report from the live site, rebuilt as small matches.
"""

import pytest

from pivot_core.domain import ExplanationSentence, Narrative, Substitution, ViewerPrefs
from pivot_worker import explainer as ex
from pivot_worker.testing import FakeStats, claim, event
from pivot_worker.verifier import verify


def card(*texts, lang="en", evidence=(), claims=(), headline=None):
    headline = headline or {"zh": "换人改变比赛", "es": "Los cambios inclinan el partido"}.get(lang, "Changes swing it")
    sentences = [ExplanationSentence(text=t, evidence_ids=list(evidence), claims=list(claims)) for t in texts]
    return Narrative(prefs=ViewerPrefs(language=lang), headline=headline, sentences=sentences, source="llm")


def issues(narrative, events, *, stats=None, minute=85, **kw):
    verdict = verify(narrative, pivot_minute=minute, events=events, stats=stats or FakeStats({}), **kw)
    return [(i.code, i.message) for i in verdict.issues]


# --- #186: M-seed-41 p85. At 78' h10 Z. Vikkaa went off for h17 N. Tolison, at 84' h06 U. Rennokasen
# for h13 A. Tesvikkaer. The cards said "H.06", named P. Nominoson (not in either change) and wrote 86'.

PLAYERS = {"h10": "Z. Vikkaa", "h17": "N. Tolison", "h06": "U. Rennokasen", "h13": "A. Tesvikkaer",
           "h08": "P. Nominoson"}
TEAMS_41 = {"home": "Harbour City", "away": "Northgate Rovers"}


@pytest.fixture
def subs():
    first = event("m078-s01500", 77, "substitution",
                  substitution=Substitution(player_off_id="h10", player_on_id="h17", slot=10, reason="fatigue"))
    second = event("m084-s01600", 83, "substitution",
                   substitution=Substitution(player_off_id="h06", player_on_id="h13", slot=6, reason="fatigue"))
    assert (first.clock_label, second.clock_label) == ("78'", "84'")
    return {e.event_id: e for e in (first, second)}


def test_186_a_player_id_written_as_a_name_is_sent_back(subs):
    bad = card("A. Tesvikkaer came on for H.06 and Harbour City held on.", evidence=["m084-s01600"])
    found = issues(bad, subs, team_names=TEAMS_41, player_names=PLAYERS)
    assert [c for c, _ in found] == ["evidence_invalid"]
    assert "'H.06', a player id" in found[0][1] and "U. Rennokasen" in found[0][1]
    good = card("A. Tesvikkaer came on for U. Rennokasen and Harbour City held on.", evidence=["m084-s01600"])
    assert issues(good, subs, team_names=TEAMS_41, player_names=PLAYERS) == []


def test_186_a_number_after_a_word_is_not_a_player_id(subs):
    # Spanish "de 3 a 11" is not the player a11 (#186's id check, found on the demo's templates).
    text = card("Harbour City pasó de 3 a 11 pases tras el cambio de A. Tesvikkaer.", lang="es",
                evidence=["m084-s01600"])
    assert not [m for _, m in issues(text, subs, team_names=TEAMS_41, player_names={**PLAYERS, "a11": "X. Other"})
                if "player id" in m]


def test_186_a_player_who_is_not_in_the_cited_events_is_sent_back(subs):
    bad = card("A. Tesvikkaer reemplazó a P. Nominoson al 84′.", lang="es", evidence=["m084-s01600"])
    found = issues(bad, subs, team_names=TEAMS_41, player_names=PLAYERS)
    assert [c for c, _ in found] == ["evidence_invalid"]
    assert "names P. Nominoson, who is not in the events it cites" in found[0][1]
    assert "U. Rennokasen" in found[0][1] and "A. Tesvikkaer" in found[0][1]
    good = card("A. Tesvikkaer reemplazó a U. Rennokasen al 84′.", lang="es", evidence=["m084-s01600"])
    assert issues(good, subs, team_names=TEAMS_41, player_names=PLAYERS) == []


def test_186_a_minute_that_is_not_the_cited_events_is_sent_back(subs):
    bad = card("86′时Harbour City用N. Tolison和A. Tesvikkaer换下了两名体能不足的球员。", lang="zh",
               evidence=["m078-s01500", "m084-s01600"])
    found = issues(bad, subs, team_names=TEAMS_41, player_names=PLAYERS)
    assert [c for c, _ in found] == ["evidence_invalid"]
    assert "says 86', but the events it cites are at 78', 84'" in found[0][1]
    good = card("78′和84′，Harbour City用N. Tolison和A. Tesvikkaer换下了两名体能不足的球员。", lang="zh",
                evidence=["m078-s01500", "m084-s01600"])
    assert issues(good, subs, team_names=TEAMS_41, player_names=PLAYERS) == []


def test_186_the_pivot_clock_is_not_an_event_and_the_headline_names_are_checked_too(subs):
    # 86' is this pivot's own clock: the live card wrote it for the changes made at 78' and 84' (#186).
    at_pivot = card("By 86' A. Tesvikkaer had settled in.", evidence=["m084-s01600"])
    found = issues(at_pivot, subs, team_names=TEAMS_41, player_names=PLAYERS)
    assert [c for c, _ in found] == ["evidence_invalid"] and "says 86'" in found[0][1]
    headline = card("A. Tesvikkaer came on for U. Rennokasen.", evidence=["m084-s01600"],
                    headline="Nominoson fades away")
    found = issues(headline, subs, team_names=TEAMS_41, player_names=PLAYERS)
    assert [c for c, _ in found] == ["evidence_invalid"] and "The headline names Nominoson" in found[0][1]


def test_186_the_explainer_sees_every_name_a_substitution_involves(subs):
    line = ex.event_line(subs["m084-s01600"], TEAMS_41, PLAYERS)
    assert line["substitution"]["player_off"] == "U. Rennokasen"
    assert line["substitution"]["player_on"] == "A. Tesvikkaer"


# --- #187: M-seed-505 p10 swung the momentum to the away side (Northgate Rovers), but the card said it
# went to Harbour City after their goal.

TEAMS_505 = {"home": "Harbour City", "away": "Northgate Rovers"}


@pytest.fixture
def goal():
    g = event("m007-s00120", 6, "shot", shot_outcome="goal", player_id="h09")
    assert g.clock_label == "7'"
    return {g.event_id: g}


@pytest.mark.parametrize("lang,text", [
    ("en", "J. Dartesmison scored at 7', swinging momentum strongly to Harbour City."),
    ("en", "Harbour City seized the momentum after the goal at 7'."),
    ("en", "After 7' Northgate Rovers lost the momentum."),
    ("en", "The goal at 7' pulled the momentum away from Northgate Rovers."),
    ("zh", "7′进球后，比赛势头倒向Harbour City。"),
    ("zh", "7′进球后，Harbour City掌握了比赛势头。"),
    ("es", "Tras el gol del 7′, el impulso pasó a Harbour City."),
    ("es", "Tras el gol del 7′, Northgate Rovers perdió el impulso."),
])
def test_187_momentum_given_to_the_wrong_side_is_sent_back(goal, lang, text):
    found = issues(card(text, lang=lang, evidence=["m007-s00120"]), goal, minute=10, team_names=TEAMS_505,
                   direction="away")
    assert [c for c, _ in found] == ["direction_mismatch"]
    assert "the momentum went to Northgate Rovers" in found[0][1]
    # The same words are right when the pivot did swing to Harbour City.
    assert issues(card(text, lang=lang, evidence=["m007-s00120"]), goal, minute=10, team_names=TEAMS_505,
                  direction="home") == []


@pytest.mark.parametrize("lang,text", [
    ("en", "From there the momentum swung towards Northgate Rovers."),
    ("en", "From there Harbour City lost their grip on the game."),
    ("zh", "此后比赛势头倒向Northgate Rovers。"),
    ("zh", "此后Harbour City失去了比赛势头。"),
    ("es", "A partir de ahí el impulso pasó a Northgate Rovers."),
    ("es", "A partir de ahí Harbour City perdió el impulso."),
])
def test_187_the_template_momentum_sentences_still_pass(goal, lang, text):
    # Both ways the template says it: for the side the pivot favoured, and for a focus team that lost it.
    assert issues(card(text, lang=lang, evidence=["m007-s00120"]), goal, minute=10, team_names=TEAMS_505,
                  direction="away") == []


def test_187_the_headline_is_checked_too(goal):
    narrative = card("J. Dartesmison scored at 7'.", evidence=["m007-s00120"], headline="Harbour City seize the momentum")
    found = issues(narrative, goal, minute=10, team_names=TEAMS_505, direction="away")
    assert [c for c, _ in found] == ["direction_mismatch"] and found[0][1].startswith("The headline says")


# --- #254: the demo's second moment read PPDA 6.0 -> 3.75 as fewer defensive actions; a lower PPDA is a
# harder press. Its first moment in Chinese called field tilt 控球率 (possession).

PPDA = [claim("ppda", "home", (57, 62), 6.0), claim("ppda", "home", (62, 67), 3.75)]
PPDA_STATS = FakeStats({("ppda", "home", (57, 62)): 6.0, ("ppda", "home", (62, 67)): 3.75})


@pytest.fixture
def press_events():
    e = event("m062-s01042", 61, "tactical_shift")
    return {e.event_id: e}


@pytest.mark.parametrize("lang,text", [
    ("en", "Harbour City's PPDA fell from 6 to 3.75, meaning fewer defensive actions."),
    ("en", "Harbour City's PPDA dropped from 6 to 3.75 as they pressed less."),
    ("zh", "Harbour City的PPDA从6降到3.75，说明防守动作更少。"),
    ("es", "El PPDA de Harbour City bajó de 6 a 3.75: menos presión."),
])
def test_254_ppda_read_the_wrong_way_round_is_sent_back(press_events, lang, text):
    found = issues(card(text, lang=lang, evidence=["m062-s01042"], claims=PPDA), press_events, minute=62,
                   stats=PPDA_STATS, team_names=TEAMS_505)
    assert [c for c, _ in found] == ["direction_mismatch"]
    assert "a lower" in found[0][1] and "more intense press" in found[0][1]


@pytest.mark.parametrize("lang,text", [
    ("en", "Harbour City's PPDA fell from 6 to 3.75 as they pressed harder."),
    ("zh", "Harbour City的PPDA从6降到3.75，逼抢更凶了。"),
])
def test_254_ppda_read_the_right_way_round_passes(press_events, lang, text):
    assert issues(card(text, lang=lang, evidence=["m062-s01042"], claims=PPDA), press_events, minute=62,
                  stats=PPDA_STATS, team_names=TEAMS_505) == []


def test_254_field_tilt_written_as_possession_in_chinese_is_sent_back(press_events):
    tilt = [claim("field_tilt_pct", "home", (62, 67), 64.0)]
    stats = FakeStats({("field_tilt_pct", "home", (62, 67)): 64.0})
    wrong = card("此后五分钟，Harbour City的控球率达到64%。", lang="zh", evidence=["m062-s01042"], claims=tilt)
    found = issues(wrong, press_events, minute=62, stats=stats, team_names=TEAMS_505)
    assert [c for c, _ in found] == ["number_mismatch"] and "场地倾斜度" in found[0][1]
    right = card("此后五分钟，Harbour City的场地倾斜度达到64%。", lang="zh", evidence=["m062-s01042"], claims=tilt)
    assert issues(right, press_events, minute=62, stats=stats, team_names=TEAMS_505) == []


def test_254_the_translator_and_the_explainer_are_told_the_right_names_and_directions():
    from pivot_worker.languages import GLOSSARY
    assert "场地倾斜度 (never 控球率)" in GLOSSARY["zh"]["field tilt"]
    prompt = ex.system_prompt(ViewerPrefs(), TEAMS_505)
    text = prompt.text if hasattr(prompt, "text") else str(prompt)
    assert "a rise means" in text and "a fall means a more intense press" in text


# --- #208: M-seed-29 39'. Three drafts called the threat-created numbers "momentum"; the Verifier said
# so each time in words the writer could not act on, and the card fell back to the template.

THREAT = [claim("threat_total", "home", (34, 39), 0.21), claim("threat_total", "home", (39, 44), 0.57)]
THREAT_STATS = FakeStats({("threat_total", "home", (34, 39)): 0.21, ("threat_total", "home", (39, 44)): 0.57})


@pytest.fixture
def red_card():
    e = event("m038-s00678", 37, "card", team="away")
    return {e.event_id: e}


def test_208_a_threat_number_called_momentum_gets_a_message_the_writer_can_act_on(red_card):
    wrong = card("After the red card, Harbour City's momentum rose from 0.21 to 0.57.", evidence=["m038-s00678"],
                 claims=THREAT)
    found = issues(wrong, red_card, minute=39, stats=THREAT_STATS, team_names=TEAMS_505)
    assert {c for c, _ in found} == {"number_mismatch"}
    message = found[0][1]
    assert "is threat created (`threat_total`), not momentum (`momentum_avg`)" in message
    assert "call it 'threat created'" in message and "swing index" in message
    # Doing what the message says passes.
    fixed = card("After the red card, Harbour City's threat created rose from 0.21 to 0.57.",
                 evidence=["m038-s00678"], claims=THREAT)
    assert issues(fixed, red_card, minute=39, stats=THREAT_STATS, team_names=TEAMS_505) == []


def test_208_the_same_in_chinese(red_card):
    wrong = card("红牌之后，Harbour City的势头从0.21上升到0.57。", lang="zh", evidence=["m038-s00678"], claims=THREAT)
    found = issues(wrong, red_card, minute=39, stats=THREAT_STATS, team_names=TEAMS_505)
    assert found and all(c == "number_mismatch" for c, _ in found) and "威胁值" in found[0][1]
    fixed = card("红牌之后，Harbour City的威胁值从0.21上升到0.57。", lang="zh", evidence=["m038-s00678"], claims=THREAT)
    assert issues(fixed, red_card, minute=39, stats=THREAT_STATS, team_names=TEAMS_505) == []


def test_208_the_explainer_prompt_keeps_threat_and_momentum_apart():
    prompt = ex.system_prompt(ViewerPrefs(), TEAMS_505)
    text = prompt.text if hasattr(prompt, "text") else str(prompt)
    assert "`threat_total` (threat created) and `momentum_avg` (momentum) are different stats" in text
