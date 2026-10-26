import pytest

from pivot_core.domain import ExplanationSentence, Narrative, PivotCandidate, ViewerPrefs
from pivot_worker import explainer as ex
from pivot_worker.languages import length
from pivot_worker.template import template_explain
from pivot_worker.testing import claim
from pivot_worker.verifier import numbers_in, verify

TEAMS = {"home": "Rovers", "away": "Harbour"}
LANGS = ("en", "zh", "es")
RISE = [claim("passes_final_third", "home", (56, 61), 3), claim("passes_final_third", "home", (61, 66), 9)]


def candidate():
    return PivotCandidate(match_id="M-test", minute=63, direction="home", cusum_stat=4.2, swing=0.3,
                          key_event_ids=["m063-s01042"], window=(58, 68))


def card(lang, text, claims=(), headline=None):
    headline = headline or ("Rovers接管比赛" if lang == "zh" else "Rovers take over")
    return Narrative(prefs=ViewerPrefs(language=lang), headline=headline, source="llm",
                     sentences=[ExplanationSentence(text=text, evidence_ids=["m063-s01042"], claims=list(claims))])


def codes(narrative, events, stats):
    return [i.code for i in verify(narrative, pivot_minute=63, events=events, stats=stats).issues]


@pytest.mark.parametrize("lang", LANGS)
def test_templates_pass_in_every_language_with_the_same_numbers(events, stats, lang):
    versions = {lg: template_explain(candidate(), events=events, stats=stats, team_names=TEAMS,
                                     prefs=ViewerPrefs(language=lg)) for lg in LANGS}
    narrative = versions[lang]
    assert verify(narrative, pivot_minute=63, events=events, stats=stats).passed
    assert [s.claims for s in narrative.sentences] == [s.claims for s in versions["en"].sentences]
    assert [s.evidence_ids for s in narrative.sentences] == [s.evidence_ids for s in versions["en"].sentences]


def test_template_wording_is_translated(events, stats):
    zh = template_explain(candidate(), events=events, stats=stats, team_names=TEAMS, prefs=ViewerPrefs(language="zh"))
    es = template_explain(candidate(), events=events, stats=stats, team_names=TEAMS, prefs=ViewerPrefs(language="es"))
    assert zh.headline == "Rovers换人改变平衡" and "威胁值从0.21上升到0.57" in zh.sentences[1].text
    assert es.sentences[1].text.startswith("En los cinco minutos siguientes, la amenaza creada de Rovers subió")


@pytest.mark.parametrize("lang,text,expected", [
    ("zh", "替补登场后，Rovers的前场传球从3上升到9。", []),
    ("zh", "替补登场后，Rovers的前场传球从3下降到9。", ["direction_mismatch"]),
    ("zh", "Rovers的前场传球从3上升到12。", ["number_mismatch"]),
    ("es", "Tras el cambio, los pases al último tercio de Rovers subieron de 3 a 9 y aumentó la presión.", []),
    ("es", "Los pases al último tercio de Rovers bajó de 3 a 9.", ["direction_mismatch"]),
])
def test_numbers_and_direction_are_checked_in_chinese_and_spanish(events, stats, lang, text, expected):
    assert codes(card(lang, text, RISE), events, stats) == expected


def test_language_specific_banned_and_significance_words(events, stats):
    assert codes(card("zh", "Rovers一定会赢。"), events, stats) == ["banned_term"]
    assert codes(card("zh", "换人带来了显著变化。"), events, stats) == ["significance_unsupported"]
    assert codes(card("es", "Rovers siempre dominó."), events, stats) == ["banned_term"]


@pytest.mark.parametrize("lang,headline,ok", [
    ("es", "Dos goles en tres minutos", False),
    ("es", "Un cambio inclina la balanza", True),
    ("zh", "三分钟内两球", False),
    ("zh", "一张牌改变比赛", True),
    ("zh", "前场三区十分危险", True),
])
def test_headline_number_words_per_language(events, stats, lang, headline, ok):
    assert codes(card(lang, "替补" if lang == "zh" else "Cambio.", headline=headline), events, stats) == (
        [] if ok else ["number_mismatch"])


def test_length_limits_per_language(events, stats):
    assert length("Rovers的前场传球明显增多", "zh") == 10
    assert codes(card("zh", "很" * 61), events, stats) == ["too_long"]
    assert codes(card("zh", "很" * 60), events, stats) == []
    assert codes(card("zh", "替补", headline="一" * 17), events, stats) == ["too_long"]


def test_number_formats_and_minutes():
    assert numbers_in("第63分钟后传球从３升到９", "zh") == ["3", "9"]
    assert numbers_in("En el minuto 61 los goles esperados subieron a 0,84", "es") == ["0.84"]
    assert numbers_in("m063 shows 4", "en") == ["4"]
    assert numbers_in("Rovers在62'换人，45+2'时又换", "zh") == []


@pytest.mark.parametrize("lang,phrase", [("zh", "Simplified Chinese"), ("es", "Spanish"), ("en", "Write in English")])
def test_prompt_asks_for_the_language(lang, phrase):
    assert phrase in ex.system_prompt(ViewerPrefs(language=lang), TEAMS).text
