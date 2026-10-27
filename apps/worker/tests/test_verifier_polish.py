"""Leftovers from the #117 review (Dx7). Each test failed before the fix."""

import pytest

from pivot_core.domain import ExplanationSentence, Narrative, OutcomeDist, PivotCandidate, SimResult, ViewerPrefs
from pivot_worker import comparator as cmp
from pivot_worker.template import template_explain
from pivot_worker.testing import FakeStats, claim, event
from pivot_worker.verifier import NO_EVIDENCE, numbers_in, verify

TEAMS = {"home": "Rovers", "away": "Harbour"}
RISE = [claim("passes_final_third", "home", (56, 61), 3), claim("passes_final_third", "home", (61, 66), 9)]
DOUBLE = FakeStats({("passes_final_third", "home", (56, 61)): 3, ("passes_final_third", "home", (61, 66)): 6})


def card(text, claims=(), lang="en", context_ids=()):
    sentence = ExplanationSentence(text=text, evidence_ids=["m063-s01042"], claims=list(claims),
                                   context_ids=list(context_ids))
    return Narrative(prefs=ViewerPrefs(language=lang), headline="Rovers", source="llm", sentences=[sentence])


def codes(narrative, events, stats, **kw):
    return [i.code for i in verify(narrative, pivot_minute=63, events=events, stats=stats, **kw).issues]


def candidate(key=("m063-s01042",)):
    return PivotCandidate(match_id="M-test", minute=63, direction="home", cusum_stat=4.2, swing=0.3,
                          key_event_ids=list(key), window=(58, 68))


# 1. With nothing to cite, the template cites nothing made up, says so, and still passes.
@pytest.mark.parametrize("which", ["none", "quiet"])
def test_template_without_events_cites_no_made_up_evidence(events, stats, which):
    evs = {} if which == "none" else {"m063-s00100": events["m063-s00100"]}      # minute 20 only
    for lang in ("en", "zh", "es"):
        narrative = template_explain(candidate(key=("m063-s01042",)), events=evs, stats=stats,
                                     prefs=ViewerPrefs(language=lang))
        cited = {e for s in narrative.sentences for e in s.evidence_ids}
        assert cited == {NO_EVIDENCE}
        assert all(not s.claims and not s.context_ids for s in narrative.sentences)
        verdict = verify(narrative, pivot_minute=63, events=evs, stats=stats)
        assert verdict.passed, verdict.issues


def test_no_evidence_is_only_for_template_sentences_without_numbers_when_nothing_is_citable(events, stats):
    def narrative(text, source="template", claims=()):
        return Narrative(prefs=ViewerPrefs(), headline="Momentum swings", source=source, sentences=[
            ExplanationSentence(text=text, evidence_ids=[NO_EVIDENCE], claims=list(claims))])

    plain = "The match turned around this point."
    assert codes(narrative(plain), {}, stats) == []
    assert codes(narrative(plain), events, stats) == ["evidence_invalid"]          # there were events to cite
    assert codes(narrative(plain, source="llm"), {}, stats) == ["evidence_invalid"]
    assert "evidence_invalid" in codes(narrative("Final-third passes reached 9.", claims=RISE[1:]), {}, stats)


# 2. Match minutes written as words or ordinals are not claims; wrong stats still fail.
@pytest.mark.parametrize("lang,text", [
    ("en", "Okafor came on in the 62nd and final-third passes rose from 3 to 9."),
    ("en", "Okafor came on at minute 62 and final-third passes rose from 3 to 9."),
    ("en", "In the 62nd minute, final-third passes rose from 3 to 9."),
    ("en", "At the 62nd minute Rovers' final-third passes had risen from 3 to 9."),
    ("en", "After minute 62, final-third passes rose from 3 to 9."),
    ("es", "Okafor entró en el 62 y los pases al último tercio de Rovers subieron de 3 a 9."),
    ("es", "Desde el minuto 62, los pases al último tercio de Rovers subieron de 3 a 9."),
    ("es", "En el minuto 62 los pases al último tercio de Rovers ya habían subido de 3 a 9."),
    ("zh", "第62分钟，Rovers的前场传球从3上升到9。"),
])
def test_minutes_in_words_are_not_claims(events, stats, lang, text):
    assert codes(card(text, RISE, lang), events, stats) == []


@pytest.mark.parametrize("text", [
    "In the 61st minute, passes rose from 3 to 12.",
    "After minute 61, passes rose from 3 to 12.",
    "Rovers had their 12th final-third pass by then.",
])
def test_minute_wording_does_not_hide_wrong_numbers(events, stats, text):
    assert "number_mismatch" in codes(card(text, RISE), events, stats)


def test_minute_wording_is_masked_but_counts_are_kept():
    assert numbers_in("In the 61st minute, passes rose from 3 to 12.") == ["3", "12"]
    assert numbers_in("en el 63, de 3 a 9; un 63% de acierto", "es") == ["3", "9", "63"]


# 3. Typographic minus signs.
@pytest.mark.parametrize("minus", ["-", "–", "−"])
def test_every_minus_sign_is_a_minus(events, minus):
    momentum = FakeStats({("momentum_avg", "home", (61, 66)): -0.32})
    claims = [claim("momentum_avg", "home", (61, 66), -0.32)]
    assert codes(card(f"Rovers' momentum was {minus}0.32 after the change.", claims), events, momentum) == []
    assert numbers_in(f"momentum {minus}0.32 in the 56–61 window") == ["-0.32", "56", "61"]


# 4. "Three times as many" style multiples are checked against the ratio.
@pytest.mark.parametrize("lang,text", [
    ("en", "Rovers made three times as many final-third passes after the change, 9 against 3."),
    ("en", "Rovers made 3 times more final-third passes, rising from 3 to 9."),
    ("zh", "Rovers的前场传球从3上升到9，是之前的三倍。"),
    ("es", "Los pases al último tercio de Rovers subieron de 3 a 9, el triple que antes."),
])
def test_multiples_are_checked_against_the_ratio(events, stats, lang, text):
    assert codes(card(text, RISE, lang), events, stats) == []
    assert codes(card(text.replace("9", "6"), [RISE[0], claim("passes_final_third", "home", (61, 66), 6)], lang),
                 events, DOUBLE) == ["number_mismatch"]


def test_a_multiple_needs_two_claims(events, stats):
    lone = card("Rovers made three times as many final-third passes.", RISE[:1])
    assert codes(lone, events, stats) == ["number_mismatch"]


def test_counting_times_is_not_a_multiple(events):
    shots = FakeStats({("shots", "home", (61, 66)): 3})
    assert codes(card("Rovers had 3 shots, hitting the post three times.", [claim("shots", "home", (61, 66), 3)]),
                 events, shots) == []


# 5. Spanish template: plural subjects take plural verbs.
@pytest.mark.parametrize("audience,label", [("analyst", "los pases al último tercio"),
                                            ("fan", "los pases cerca del área rival")])
def test_spanish_template_agrees_in_number(events, audience, label):
    passes = FakeStats({("passes_final_third", "home", (58, 63)): 3, ("passes_final_third", "home", (63, 68)): 9})
    narrative = template_explain(candidate(), events=events, stats=passes, team_names=TEAMS,
                                 prefs=ViewerPrefs(language="es", audience=audience))
    stat = next(s.text for s in narrative.sentences if s.claims)
    assert f"{label} de Rovers subieron" in stat
    assert verify(narrative, pivot_minute=63, events=events, stats=passes).passed


def test_spanish_template_keeps_singular_verbs_for_singular_subjects(events):
    threat = FakeStats({("threat_total", "home", (58, 63)): 0.21, ("threat_total", "home", (63, 68)): 0.57})
    narrative = template_explain(candidate(), events=events, stats=threat, team_names=TEAMS,
                                 prefs=ViewerPrefs(language="es"))
    assert "la amenaza creada de Rovers subió" in next(s.text for s in narrative.sentences if s.claims)


# 6. Off-pitch stories told in other words still need a context item.
@pytest.mark.parametrize("lang,text", [
    ("en", "Okafor scored against the team that let him go."),
    ("en", "On his return to his old ground, Okafor changed the game."),
    ("en", "The former Harbour man drove at the back line."),
    ("en", "Okafor came back to haunt his boyhood club."),
    ("en", "Okafor ran at his old teammates."),
    ("zh", "Okafor对阵当年放走他的球队时打进一球。"),
    ("zh", "Okafor回到旧主场后改变了比赛。"),
    ("zh", "Okafor面对母队毫不手软。"),
    ("es", "Okafor marcó ante el equipo que lo dejó ir."),
    ("es", "Okafor volvió a su antiguo estadio y cambió el partido."),
    ("es", "El exjugador del Harbour encaró a la defensa."),
    ("es", "Okafor desbordó a sus excompañeros."),
])
def test_paraphrased_off_pitch_stories_need_context(events, stats, lang, text):
    assert codes(card(text, lang=lang), events, stats) == ["context_invalid"]


@pytest.mark.parametrize("lang,text", [
    ("en", "Harbour's defence let him go past too easily."),
    ("en", "Okafor returned to his old position on the left."),
    ("en", "The former shape left gaps; the new one closed them."),
    ("en", "Okafor let fly from the edge of the box."),
    ("zh", "Rovers的后卫放走了他，Okafor直插禁区。"),
    ("zh", "Okafor回到原来的位置。"),
    ("es", "La defensa de Harbour lo dejó pasar."),
    ("es", "Okafor volvió a su posición en la izquierda."),
])
def test_ordinary_sentences_are_not_off_pitch_stories(events, stats, lang, text):
    assert codes(card(text, lang=lang), events, stats) == []


# 7. "X were more likely to win" names X's win.
CMP_TEAMS = {"home": "Harbour City", "away": "Northvale Rovers"}
CMP_EVENTS = {"m063-s02302": event("m063-s02302", 62, "substitution")}
CI = {"home_win": (0.3, 0.38), "draw": (0.3, 0.4), "away_win": (0.25, 0.35)}


def compare(text, lang="en"):
    base = OutcomeDist(home_win=0.34, draw=0.36, away_win=0.30, ci95=CI)
    cf = OutcomeDist(home_win=0.52, draw=0.28, away_win=0.20, ci95=CI)
    result = SimResult(scenario_id="M-test:s1", baseline=base, counterfactual=cf,
                       significant={"home_win": True, "draw": False, "away_win": False},
                       runtime_ms=900, executor="local_pool")
    narrative = Narrative(prefs=ViewerPrefs(language=lang), headline="保留Moreau" if lang == "zh" else "Keeping Moreau on", source="llm",
                          sentences=[ExplanationSentence(text=text, evidence_ids=["m063-s02302"])])
    verdict = cmp.verify_comparison(narrative, result, at_minute=62, events=CMP_EVENTS, stats=FakeStats({}),
                                    team_names=CMP_TEAMS, target_event_id="m063-s02302")
    return [i.code for i in verdict.issues]


@pytest.mark.parametrize("text,ok", [
    ("Harbour City were more likely to win in the replays.", True),
    ("Harbour City were more likely to win than Northvale Rovers.", True),
    ("Northvale Rovers became less likely to win.", True),
    ("With Moreau on, Harbour City looked likelier to win in the replays.", True),
    ("Harbour City were less likely to win in the replays.", False),
    ("Northvale Rovers became more likely to win.", False),
])
def test_team_likely_to_win_names_that_teams_win(text, ok):
    assert compare(text) == ([] if ok else ["direction_mismatch"])


@pytest.mark.parametrize("text,ok", [("保留Moreau后，Harbour City更有可能获胜。", True),
                                     ("保留Moreau后，Northvale Rovers更有可能获胜。", False)])
def test_team_likely_to_win_in_chinese(text, ok):
    assert compare(text, "zh") == ([] if ok else ["direction_mismatch"])
