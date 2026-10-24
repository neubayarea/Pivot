"""Counter-examples from the #82 review (Dx2): wrong numbers and directions in Chinese and Spanish."""

import pytest

from pivot_core.domain import ExplanationSentence, Narrative, OutcomeDist, PivotCandidate, SimResult, ViewerPrefs
from pivot_worker import comparator as cmp
from pivot_worker.template import template_explain
from pivot_worker.testing import FakeStats, claim, event
from pivot_worker.verifier import numbers_in, verify

TEAMS = {"home": "Rovers", "away": "Harbour"}
RISE = [claim("passes_final_third", "home", (56, 61), 3), claim("passes_final_third", "home", (61, 66), 9)]
FALL = [claim("pass_accuracy_pct", "home", (56, 61), 74.2), claim("pass_accuracy_pct", "home", (61, 66), 68.4)]


def card(lang, text, claims=(), audience="analyst"):
    return Narrative(prefs=ViewerPrefs(language=lang, audience=audience), headline="Rovers", source="llm",
                     sentences=[ExplanationSentence(text=text, evidence_ids=["m063-s01042"], claims=list(claims))])


def codes(narrative, events, stats):
    return [i.code for i in verify(narrative, pivot_minute=63, events=events, stats=stats).issues]


# 1. Numbers written as words are checked like digits.
@pytest.mark.parametrize("lang,text,expected", [
    ("zh", "Rovers的前场传球从三上升到十二。", ["number_mismatch"]),
    ("zh", "Rovers的前场传球从三上升到九。", []),
    ("zh", "Rovers的前场传球多了十二次。", ["number_mismatch"]),
    ("es", "Los pases al último tercio de Rovers subieron de tres a doce.", ["number_mismatch"]),
    ("es", "Los pases al último tercio de Rovers subieron de tres a nueve.", []),
    ("en", "Rovers' final-third passes rose from three to twelve.", ["number_mismatch"]),
])
def test_numbers_written_as_words_are_checked(events, stats, lang, text, expected):
    assert codes(card(lang, text, RISE), events, stats) == expected


def test_everyday_words_with_numerals_are_not_numbers():
    assert numbers_in("Rovers在61'吃到一张牌，这一刻进入前场三区的传球变多", "zh") == []
    assert numbers_in("此后五分钟，Rovers的威胁值从0.21上升到0.57。", "zh") == ["0.21", "0.57"]
    assert numbers_in("En los cinco minutos siguientes, Rovers vio una tarjeta", "es") == []
    assert numbers_in("in the next five minutes", "en") == []


# 2. More direction words, and "from A to B" must follow the claims' order.
@pytest.mark.parametrize("lang,text,claims", [
    ("es", "Los pases al último tercio de Rovers bajaron de 3 a 9.", RISE),
    ("es", "Los pases al último tercio de Rovers cayeron de 3 a 9.", RISE),
    ("zh", "Rovers的前场传球从3跌到9。", RISE),
    ("zh", "Rovers的前场传球从3回落到9。", RISE),
    ("zh", "Rovers的传球成功率从74.2增多到68.4。", FALL),
    ("es", "La precisión de pase de Rovers subieron de 74,2 a 68,4.", FALL),
])
def test_more_direction_words(events, stats, lang, text, claims):
    assert codes(card(lang, text, claims), events, stats) == ["direction_mismatch"]


@pytest.mark.parametrize("lang,text", [
    ("en", "Rovers' final-third passes went from 9 to 3."),
    ("zh", "Rovers的前场传球从9变成3。"),
    ("es", "Los pases al último tercio de Rovers pasaron de 9 a 3."),
])
def test_from_to_must_follow_the_order_of_the_windows(events, stats, lang, text):
    assert codes(card(lang, text, RISE), events, stats) == ["direction_mismatch"]


# 3. Magnitude words are checked against the ratio, not just the sign.
@pytest.mark.parametrize("lang,text,expected", [
    ("en", "Rovers' final-third passes doubled from 3 to 9.", ["number_mismatch"]),
    ("en", "Rovers' final-third passes tripled from 3 to 9.", []),
    ("zh", "Rovers的前场传球翻倍，从3到9。", ["number_mismatch"]),
    ("zh", "Rovers的前场传球翻了两番，从3到9。", ["number_mismatch"]),
    ("es", "Los pases al último tercio de Rovers se duplicaron, de 3 a 9.", ["number_mismatch"]),
    ("es", "Los pases al último tercio de Rovers se triplicaron, de 3 a 9.", []),
])
def test_magnitude_words_are_checked(events, stats, lang, text, expected):
    assert codes(card(lang, text, RISE), events, stats) == expected


# 4. A number in Chinese single quotes is a number, not a match minute.
def test_quoted_numbers_are_not_minutes(events, stats):
    assert numbers_in("Rovers的‘12’次前场传球", "zh") == ["12"]
    assert codes(card("zh", "Rovers的前场传球达到‘12’次。", RISE), events, stats) == ["number_mismatch"]
    assert numbers_in("Rovers在62’换人", "zh") == []


# 5. Spanish thousands separator.
def test_spanish_thousands_separator(events):
    stats = FakeStats({("distance_covered_km", "home", (56, 61)): 9000.0})
    km = [claim("distance_covered_km", "home", (56, 61), 9000.0)]
    assert numbers_in("Rovers recorrieron 9.000 km y 0,84 xG.", "es") == ["9000", "0.84"]
    assert codes(card("es", "Rovers recorrieron 9.000 km.", km), events, stats) == []
    assert codes(card("es", "Rovers recorrieron 9.000 km.", [claim("distance_covered_km", "home", (56, 61), 9.0)]),
                 events, FakeStats({("distance_covered_km", "home", (56, 61)): 9.0})) == ["number_mismatch"]


# 6. Comparisons name outcomes in Chinese and Spanish, and the fallback speaks the language.
CMP_TEAMS = {"home": "Harbour City", "away": "Northvale Rovers"}
CMP_EVENTS = {"m063-s02302": event("m063-s02302", 62, "substitution")}
CI = {"home_win": (0.3, 0.38), "draw": (0.3, 0.4), "away_win": (0.25, 0.35)}


def sim(significant=False):
    base = OutcomeDist(home_win=0.34, draw=0.36, away_win=0.30, ci95=CI)
    cf = OutcomeDist(home_win=0.52, draw=0.28, away_win=0.20, ci95=CI)
    return SimResult(scenario_id="M-test:s1", baseline=base, counterfactual=cf,
                     significant={"home_win": significant, "draw": False, "away_win": False},
                     runtime_ms=900, executor="local_pool")


def compare(lang, *texts):
    narrative = Narrative(prefs=ViewerPrefs(language=lang), headline="Harbour City", source="llm",
                          sentences=[ExplanationSentence(text=t, evidence_ids=["m063-s02302"]) for t in texts])
    verdict = cmp.verify_comparison(narrative, sim(), at_minute=62, events=CMP_EVENTS, stats=FakeStats({}),
                                    team_names=CMP_TEAMS)
    return [i.code for i in verdict.issues]


@pytest.mark.parametrize("lang,good,bad", [
    ("zh", "保留Moreau后，Harbour City获胜在模拟中更有可能。", "保留Moreau后，平局在模拟中更有可能。"),
    ("es", "Con Moreau en el campo, una victoria de Harbour City fue más probable.",
     "Con Moreau en el campo, el empate fue más probable."),
])
def test_comparison_outcomes_are_named_in_every_language(lang, good, bad):
    assert compare(lang, good) == []
    assert compare(lang, bad) == ["direction_mismatch"]


@pytest.mark.parametrize("lang,word", [("zh", "更有可能"), ("es", "más probable")])
def test_comparison_fallback_is_in_the_language_and_passes(lang, word):
    narrative = cmp.template_comparison(sim(), evidence_id="m063-s02302", team_names=CMP_TEAMS,
                                        prefs=ViewerPrefs(language=lang))
    assert word in narrative.sentences[0].text
    assert cmp.verify_comparison(narrative, sim(), at_minute=62, events=CMP_EVENTS, stats=FakeStats({}),
                                 team_names=CMP_TEAMS).passed


# 7. Fan and analyst fallbacks differ in Chinese and Spanish.
@pytest.mark.parametrize("lang", ["zh", "es"])
def test_template_fan_wording_differs_from_analyst(events, stats, lang):
    candidate = PivotCandidate(match_id="M-test", minute=63, direction="home", cusum_stat=4.2, swing=0.3,
                               key_event_ids=["m063-s01042"], window=(58, 68))
    texts = {}
    for audience in ("analyst", "fan"):
        narrative = template_explain(candidate, events=events, stats=stats, team_names=TEAMS,
                                     prefs=ViewerPrefs(language=lang, audience=audience))
        assert verify(narrative, pivot_minute=63, events=events, stats=stats).passed
        texts[audience] = [s.text for s in narrative.sentences]
    assert texts["fan"] != texts["analyst"]
