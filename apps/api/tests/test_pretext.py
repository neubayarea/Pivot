"""The pre-match sentences in the page's language (Bx19, #355): fixed templates first, the model only for
what no template knows, and names and numbers exactly as in the English."""

from __future__ import annotations

import asyncio
import json
import re

import pytest
from fastapi.testclient import TestClient

from pivot_api import sims
from pivot_api.app import app
from pivot_api.pretext import NUMBERS, TEMPLATES, WORDS, PreText, from_template, sentences
from pivot_core.sim.world import CLUB_NAMES
from pivot_worker.languages import club_name_forms, has_cjk
from pivot_worker.models import ScriptedModelClient

CLUBS = ("Harbour City", "Northgate Rovers")
NAMES = {"name": "M. Miquingorini", "other": "W. Quinrenez", "coach": "S. Katoo", "team": "Northgate Rovers",
         "club": "Harbour City"}
EXAMPLE_NUMBERS = {"n": "3", "x": "7.2", "year": "2024", "a": "41,250", "c": "52,000", "i": "4"}


def seed(spec: sims.SimSpec):
    match = sims.seed_match(spec.seed, spec.home_strength, spec.away_strength, spec.home_formation,
                            spec.away_formation)
    return match.model_copy(update={"match_id": spec.match_id})


def examples(template) -> list[tuple[str, dict[str, str]]]:
    """The template's English filled in, once for every word it can pick from a list."""
    fields = re.findall(r"\{(\w+)\}", template.en)
    choice = next((f for f in fields if f in WORDS), None)
    out = []
    for word in WORDS[choice] if choice else [None]:
        params = {f: word if f == choice else next(iter(WORDS[f])) if f in WORDS else EXAMPLE_NUMBERS[f]
                  if f in NUMBERS else NAMES[f] for f in fields}
        out.append((template.en.format(**params), params))
    return out


@pytest.mark.parametrize("lang", ["zh", "es"])
@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.key)
def test_every_template_translates_with_names_and_numbers_as_written(template, lang):
    for english, params in examples(template):
        out = from_template(english, lang)
        assert out, english
        assert has_cjk(out) == (lang == "zh") and "{" not in out
        for field, value in params.items():
            if field in WORDS:
                assert value not in out and WORDS[field][value][("zh", "es").index(lang)].lower() in out.lower()
            else:
                assert value in out, (field, value, out)       # names and numbers exactly as in the English
        assert not [f for club in CLUBS for f in club_name_forms(club, lang) if f in out], out


def test_a_possessive_after_a_plural_club_name_is_the_same_template():
    out = from_template("S. Katoo under pressure after 3 defeats in Northgate Rovers' last five league games", "es")
    assert out == "S. Katoo, bajo presión tras 3 derrotas en los últimos cinco partidos de liga de Northgate Rovers"
    assert from_template("S. Katoo's Harbour City have won 4 of their last five", "zh") == "S. Katoo执教的Harbour City近五场赢了4场"


def test_every_sentence_of_every_seed_match_has_a_template():
    """What the site shows: every headline and effect note of the seed matches, and the recorded demo's news."""
    found = [s for spec in sims.SPECS for s in sentences(seed(spec))]
    demo = json.loads(sims.FIXTURE.read_text(encoding="utf-8"))["match"]["context"]
    found += [n["headline"] for n in demo["news"]] + [e["note"] for e in demo.get("effects", [])]
    assert len(found) > 100
    for lang in ("zh", "es"):
        assert [s for s in found if from_template(s, lang) is None] == []


def test_the_demo_headline_keeps_the_club_he_left_for():
    out = from_template("Harbour City fans plan a hostile welcome for A. Bersaro, who left the club for Rovers on bad "
                        "terms in 2024", "zh")
    assert out == "Harbour City球迷准备给A. Bersaro一个不友好的“欢迎”：他2024年与球队闹翻后转投Rovers"


def test_a_sentence_no_template_knows_is_left_in_english():
    assert from_template("Harbour City sell 2,000 more tickets for Northgate Rovers", "zh") is None
    assert from_template("distracted by a family matter", "es") is None    # a word outside the list


@pytest.fixture
def odd_match():
    """A seed match with one headline no template knows."""
    match = seed(sims.SPECS[0])
    news = [match.context.news[0].model_copy(update={"headline": "Harbour City sell 2,000 more tickets for "
                                                                 "the visit of Northgate Rovers"}),
            *match.context.news[1:]]
    return match.model_copy(update={"context": match.context.model_copy(update={"news": news})})


ODD = "Harbour City sell 2,000 more tickets for the visit of Northgate Rovers"


def test_without_a_model_the_unknown_sentence_stays_english(odd_match):
    out = asyncio.run(PreText(None).translate(odd_match, "zh"))
    assert out.untranslated == [ODD] and ODD not in out.texts
    assert len(out.texts) == len(sentences(odd_match)) - 1


def test_the_model_translates_the_rest_and_a_kept_translation_is_cached(odd_match):
    models = ScriptedModelClient(standard=[json.dumps({"texts": ["Harbour City为Northgate Rovers的来访多卖出2,000张票"]})])
    pretext = PreText(models)
    out = asyncio.run(pretext.translate(odd_match, "zh"))
    assert out.texts[ODD] == "Harbour City为Northgate Rovers的来访多卖出2,000张票" and out.untranslated == []
    assert json.loads(models.calls[0][1][1]["content"]) == {"texts": [ODD]}    # only what no template knows
    again = asyncio.run(pretext.translate(odd_match, "zh"))
    assert again.texts[ODD] == out.texts[ODD] and len(models.calls) == 1


@pytest.mark.parametrize("reply", [
    "海港城为Northgate Rovers的来访多卖出2,000张票",       # the club name translated (#344)
    "Harbour City为Northgate Rovers的来访多卖出两千张票",   # the number written in words
    "Harbour City为来访多卖出2,000张票",                   # a name dropped
    "Harbour City sell 2,000 more tickets for Northgate Rovers",   # not Chinese
])
def test_a_translation_that_changes_a_name_or_number_is_not_kept(odd_match, reply):
    models = ScriptedModelClient(standard=[json.dumps({"texts": [reply]})])
    out = asyncio.run(PreText(models).translate(odd_match, "zh"))
    assert ODD not in out.texts and out.untranslated == [ODD]


def test_a_model_that_fails_leaves_the_sentence_english_and_is_not_asked_again_at_once(odd_match):
    models = ScriptedModelClient(standard=["not json"])
    pretext = PreText(models)
    assert asyncio.run(pretext.translate(odd_match, "es")).untranslated == [ODD]
    assert asyncio.run(pretext.translate(odd_match, "es")).untranslated == [ODD] and len(models.calls) == 1


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PIVOT_DEMO_FIXTURE", str(sims.FIXTURE))
    monkeypatch.setenv("PIVOT_SIM_MATCHES", "0")
    monkeypatch.setenv("PIVOT_WHATIF_WARM", "0")
    monkeypatch.setenv("PIVOT_PREWARM_LANGS", "none")
    monkeypatch.setenv("PIVOT_PIPELINE", "fake")
    with TestClient(app) as c:
        yield c


def test_the_endpoint_serves_the_demo_in_each_language(client):
    match = json.loads(sims.FIXTURE.read_text(encoding="utf-8"))["match"]
    for lang in ("zh", "es"):
        r = client.get(f"/api/matches/{match['match_id']}/prematch/text", params={"lang": lang})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["lang"] == lang and body["untranslated"] == []
        assert set(body["texts"]) == {n["headline"] for n in match["context"]["news"]} | \
            {e["note"] for e in match["context"].get("effects", [])}
    assert client.get(f"/api/matches/{match['match_id']}/prematch/text", params={"lang": "fr"}).status_code == 422
    assert client.get("/api/matches/no-such-match/prematch/text", params={"lang": "zh"}).status_code == 404


def test_club_names_in_the_templates_are_the_worlds_own():
    # The examples use real club names of the world, so the club-name check above means something.
    assert set(CLUBS) <= set(CLUB_NAMES.values())
