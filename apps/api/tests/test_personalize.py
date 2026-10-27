"""A11: the pivot endpoints answer in the viewer's language and audience, and remember each version."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from pivot_api import personalize
from pivot_api.app import app
from pivot_api.demo import DEMO_MATCH_ID
from pivot_api.personalize import Personalizer
from pivot_core.domain import ExplanationSentence, Narrative, ViewerPrefs
from pivot_worker.models import ModelUnavailable, ScriptedModelClient

PIVOT_ID = f"{DEMO_MATCH_ID}:p61"
DEFAULT = {"audience": "analyst", "language": "en", "focus_team": None, "focus_player_id": None}
ZH_DRAFT = json.dumps({"headline": "换人之后流浪者掌控比赛", "sentences": [{
    "text": "流浪者换人后很快扳平比分，局势随之改变。", "evidence_ids": ["m061-s00126", "m064-s00134"]}]},
    ensure_ascii=False)
# What the translator returns for the stored English card (Ax35): texts only, in order.
ZH_TRANSLATION = json.dumps({"headline": "换人之后流浪者掌控比赛",
                             "sentences": ["换人后没几分钟，流浪者就扳平了比分，那是他们这段时间唯一的射门。"]},
                            ensure_ascii=False)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("PIVOT_PROFILE", raising=False)
    monkeypatch.delenv("PIVOT_DEMO", raising=False)
    monkeypatch.delenv("PIVOT_PIPELINE", raising=False)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def no_english(monkeypatch):
    """No English card to translate: other languages are written from scratch (the pre-Ax35 path)."""
    async def none(self, pivot, prefs):
        return None

    monkeypatch.setattr(Personalizer, "_english", none)


def use_models(models) -> Personalizer:
    app.state.personalizer = Personalizer(app.state.adapters.matches, models, stats_factory=personalize.match_stats)
    return app.state.personalizer


def stored(prefs: ViewerPrefs):
    return asyncio.run(app.state.adapters.matches.get_narrative(DEMO_MATCH_ID, PIVOT_ID, prefs))


def test_default_is_the_stored_english_analyst_version(client):
    pivot = client.get(f"/api/pivots/{PIVOT_ID}").json()
    assert pivot["prefs"] == DEFAULT
    assert pivot["narrative"]["headline"] == "Rovers seize control after the change"


@pytest.mark.parametrize("lang", ["en", "zh", "es"])
@pytest.mark.parametrize("audience", ["analyst", "fan"])
def test_every_language_and_audience(client, lang, audience):
    events = {e["event_id"] for e in client.get(f"/api/matches/{DEMO_MATCH_ID}/events").json()}
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": lang, "audience": audience}).json()
    prefs = {**DEFAULT, "language": lang, "audience": audience}
    assert pivot["prefs"] == prefs and pivot["narrative"]["prefs"] == prefs
    assert pivot["pivot_id"] == PIVOT_ID and pivot["status"] == "confirmed"
    assert all(set(s["evidence_ids"]) <= events for s in pivot["narrative"]["sentences"])
    if lang == "zh":
        assert any("一" <= ch <= "鿿" for ch in pivot["narrative"]["sentences"][0]["text"])


def test_focus_team_and_player_are_part_of_the_version(client):
    player = client.get(f"/api/matches/{DEMO_MATCH_ID}").json()["home"]["squad"][0]["player_id"]
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "es", "team": "home", "player": player}).json()
    assert pivot["prefs"] == {**DEFAULT, "language": "es", "focus_team": "home", "focus_player_id": player}


def test_list_uses_the_same_parameters(client):
    pivots = client.get(f"/api/matches/{DEMO_MATCH_ID}/pivots", params={"lang": "zh", "audience": "fan"}).json()
    assert [(p["minute"], p["prefs"]["language"], p["prefs"]["audience"]) for p in pivots] == \
        [(61, "zh", "fan"), (71, "zh", "fan")]
    assert pivots[0]["narrative"]["prefs"]["language"] == "zh"
    assert pivots[1]["narrative"] is None                          # pending: nothing written yet


def test_second_request_is_served_from_the_store(client):
    models = ScriptedModelClient(standard=[ZH_TRANSLATION])
    use_models(models)
    first = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    second = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    listed = client.get(f"/api/matches/{DEMO_MATCH_ID}/pivots", params={"lang": "zh"}).json()[0]
    assert len(models.calls) == 1
    assert first == second == listed
    assert first["narrative"]["source"] == "llm" and first["narrative"]["headline"] == "换人之后流浪者掌控比赛"
    assert stored(ViewerPrefs(language="zh")).headline == "换人之后流浪者掌控比赛"


def test_rejected_draft_is_rewritten_with_the_verifier_feedback(client, no_english):
    bad = json.dumps({"headline": "坏稿", "sentences": [{"text": "流浪者换人。", "evidence_ids": ["nope"]}]},
                     ensure_ascii=False)
    models = ScriptedModelClient(standard=[bad, ZH_DRAFT])
    use_models(models)
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    assert pivot["narrative"]["source"] == "llm" and pivot["narrative"]["verifier_attempts"] == 2
    rewrite = models.calls[1][1][1]["content"]
    assert "The Verifier rejected your previous card" in rewrite
    assert "Your previous card:" in rewrite and "坏稿" in rewrite


def test_explainer_down_falls_back_to_the_template_in_that_language(client):
    use_models(ScriptedModelClient(standard=[ModelUnavailable("429")]))
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh", "audience": "fan"}).json()
    assert pivot["prefs"]["language"] == "zh" and pivot["narrative"]["source"] == "template"


FAN = {"audience": "fan"}
FAN_DRAFT = json.dumps({"headline": "Rovers take over after the change", "sentences": [{
    "text": "Rovers levelled soon after their substitution and the game turned their way.",
    "evidence_ids": ["m061-s00126", "m064-s00134"]}]})


def test_a_model_hiccup_is_asked_once_more(client):
    models = ScriptedModelClient(standard=[ModelUnavailable("429"), FAN_DRAFT])
    use_models(models)
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params=FAN).json()
    assert pivot["narrative"]["source"] == "llm" and len(models.calls) == 2


def test_a_template_fallback_is_written_again_later(client, monkeypatch):
    # Two 429s in a row: this request gets the template. It used to stay the template until a restart (#242).
    monkeypatch.setattr(personalize, "MODEL_REST_S", 0.0)
    models = ScriptedModelClient(standard=[ModelUnavailable("429"), ModelUnavailable("429"), FAN_DRAFT])
    use_models(models)
    first = client.get(f"/api/pivots/{PIVOT_ID}", params=FAN).json()
    soon = client.get(f"/api/pivots/{PIVOT_ID}", params=FAN).json()
    assert first["narrative"]["source"] == soon["narrative"]["source"] == "template"
    assert len(models.calls) == 2                                # served from memory for a while
    monkeypatch.setattr(personalize, "FALLBACK_RETRY_S", 0.0)    # ... and once that while is over:
    later = client.get(f"/api/pivots/{PIVOT_ID}", params=FAN).json()
    assert later["narrative"]["source"] == "llm" and later["narrative"]["headline"] == "Rovers take over after the change"
    assert later["prefs"]["audience"] == "fan" and len(models.calls) == 3


def test_a_model_that_keeps_failing_rests_instead_of_being_asked_on_every_request(client, monkeypatch):
    monkeypatch.setattr(personalize, "FALLBACK_RETRY_S", 0.0)    # every request may try again
    models = ScriptedModelClient(standard=[ModelUnavailable("timeout")] * 2 + [FAN_DRAFT])
    use_models(models)
    for _ in range(3):
        assert client.get(f"/api/pivots/{PIVOT_ID}", params=FAN).json()["narrative"]["source"] == "template"
    assert len(models.calls) == 2                                # resting: not asked again for a minute


def test_nothing_passes_the_verifier_so_english_is_served(client, monkeypatch):
    def broken_template(candidate, *, prefs, chain_id, **_):
        return Narrative(prefs=prefs, headline="坏稿", source="template", chain_id=chain_id,
                         sentences=[ExplanationSentence(text="编造的事件。", evidence_ids=["made-up"])])

    monkeypatch.setattr(personalize, "template_explain", broken_template)
    use_models(ScriptedModelClient(standard=[ModelUnavailable("timeout")]))
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    assert pivot["prefs"] == DEFAULT
    assert pivot["narrative"]["headline"] == "Rovers seize control after the change"
    assert stored(ViewerPrefs(language="zh")) is None             # not remembered: tried again next time


def test_verifier_bug_serves_english_and_is_tried_again(client, monkeypatch):
    calls = []

    def broken_verify(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("stat source bug")

    monkeypatch.setattr(personalize, "verify", broken_verify)
    use_models(ScriptedModelClient(standard=[ZH_TRANSLATION, ZH_TRANSLATION]))
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"})
    assert pivot.status_code == 200 and pivot.json()["prefs"] == DEFAULT
    assert pivot.json()["narrative"]["headline"] == "Rovers seize control after the change"
    assert len(calls) == 2                                      # the translation, then the template: no retry
    assert stored(ViewerPrefs(language="zh")) is None

    monkeypatch.undo()
    again = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    assert again["prefs"]["language"] == "zh" and again["narrative"]["source"] == "llm"


def test_explainer_bug_falls_back_to_the_template(client):
    use_models(ScriptedModelClient(standard=[RuntimeError("bad reply object")]))
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"})
    assert pivot.status_code == 200
    assert pivot.json()["prefs"]["language"] == "zh" and pivot.json()["narrative"]["source"] == "template"


def test_any_failure_writing_a_version_serves_english_and_is_tried_again(client, monkeypatch):
    def broken_template(*args, **kwargs):
        raise RuntimeError("template bug")

    monkeypatch.setattr(personalize, "template_explain", broken_template)
    use_models(ScriptedModelClient(standard=[RuntimeError("explainer bug")]))
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "es"})
    assert pivot.status_code == 200 and pivot.json()["prefs"] == DEFAULT
    listed = client.get(f"/api/matches/{DEMO_MATCH_ID}/pivots", params={"lang": "es"})
    assert listed.status_code == 200 and listed.json()[0]["prefs"] == DEFAULT
    assert stored(ViewerPrefs(language="es")) is None

    monkeypatch.undo()
    use_models(None)
    again = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "es"}).json()
    assert again["prefs"]["language"] == "es" and again["narrative"]["source"] == "template"


def test_new_run_of_the_pivot_drops_the_stored_versions(client):
    repo = app.state.adapters.matches
    models = ScriptedModelClient(standard=[ZH_TRANSLATION, ZH_TRANSLATION])
    use_models(models)
    client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"})
    pivot = asyncio.run(repo.get_pivot(DEMO_MATCH_ID, PIVOT_ID))
    asyncio.run(repo.upsert_pivot(pivot.model_copy(update={"chain_id": "c-demo-61-rerun"})))
    again = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    assert len(models.calls) == 2 and again["narrative"]["chain_id"] == "c-demo-61-rerun"


def english(audience: str = "analyst") -> Narrative:
    return stored(ViewerPrefs(audience=audience)) or asyncio.run(
        app.state.adapters.matches.get_pivot(DEMO_MATCH_ID, PIVOT_ID)).narrative


def test_translation_keeps_the_evidence_and_claims_of_the_english_card(client):
    models = ScriptedModelClient(standard=[ZH_TRANSLATION])
    use_models(models)
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    source = english()
    assert pivot["narrative"]["source"] == "llm" and pivot["narrative"]["verifier_attempts"] == 1
    assert [(s["evidence_ids"], s["claims"], s["context_ids"]) for s in pivot["narrative"]["sentences"]] == \
        [(s.evidence_ids, [c.model_dump(mode="json") for c in s.claims], s.context_ids) for s in source.sentences]
    request = json.loads(models.calls[0][1][1]["content"])
    assert request == {"headline": source.headline, "sentences": [s.text for s in source.sentences]}


@pytest.mark.parametrize("bad, code", [
    (["Rovers levelled within minutes of the substitution."], "not in Simplified Chinese"),  # left in English
    (["换人后流浪者扳平了比分，射门达到5次。"], "5"),                                        # a number it never claimed
])
def test_rejected_translation_is_tried_again_then_falls_back_to_the_template(client, bad, code):
    reply = json.dumps({"headline": "换人之后流浪者掌控比赛", "sentences": bad}, ensure_ascii=False)
    models = ScriptedModelClient(standard=[reply, ZH_TRANSLATION])
    use_models(models)
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    assert pivot["narrative"]["source"] == "llm" and pivot["narrative"]["verifier_attempts"] == 2
    feedback = models.calls[1][1][-1]["content"]
    assert "The Verifier rejected that translation" in feedback and code in feedback

    models = ScriptedModelClient(standard=[reply, reply])
    use_models(models)
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh", "audience": "fan"}).json()
    assert len(models.calls) == 2
    assert pivot["prefs"]["language"] == "zh" and pivot["narrative"]["source"] == "template"


def test_unusable_translation_reply_is_tried_again(client):
    wrong_count = json.dumps({"headline": "换人", "sentences": ["一句。", "两句。"]}, ensure_ascii=False)
    models = ScriptedModelClient(standard=[wrong_count, ZH_TRANSLATION])
    use_models(models)
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    assert pivot["narrative"]["source"] == "llm" and "expected 1 sentence" in models.calls[1][1][-1]["content"]


def test_english_template_is_not_translated(client):
    repo = app.state.adapters.matches
    pivot = asyncio.run(repo.get_pivot(DEMO_MATCH_ID, PIVOT_ID))
    asyncio.run(repo.upsert_pivot(pivot.model_copy(
        update={"narrative": pivot.narrative.model_copy(update={"source": "template"})})))
    models = ScriptedModelClient(standard=[ZH_TRANSLATION])
    use_models(models)
    zh = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    assert models.calls == [] and zh["prefs"]["language"] == "zh" and zh["narrative"]["source"] == "template"


def test_prewarm_writes_both_audiences_in_each_language(client):
    use_models(None)
    written = asyncio.run(app.state.personalizer.prewarm(DEMO_MATCH_ID, ["zh", "es"], wait=0))
    assert written == 4                                          # p61 only: p71 has no English card yet
    for lang in ("zh", "es"):
        for audience in ("analyst", "fan"):
            assert stored(ViewerPrefs(language=lang, audience=audience)).prefs.language == lang


def test_an_english_card_stored_as_the_chinese_one_is_written_again(client, no_english):
    """#184: versions stored before the Verifier checked the language are not served as Chinese."""
    repo = app.state.adapters.matches
    pivot = asyncio.run(repo.get_pivot(DEMO_MATCH_ID, PIVOT_ID))
    english = pivot.narrative.model_copy(update={"prefs": ViewerPrefs(language="zh", audience="fan")})
    asyncio.run(repo.upsert_narrative(DEMO_MATCH_ID, PIVOT_ID, english))
    models = ScriptedModelClient(standard=[ZH_DRAFT])
    use_models(models)
    served = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh", "audience": "fan"}).json()
    assert len(models.calls) == 1 and served["narrative"]["headline"] == "换人之后流浪者掌控比赛"


def test_an_english_draft_for_chinese_is_sent_back(client, no_english):
    english = json.dumps({"headline": "Rovers seize control after the change", "sentences": [{
        "text": "Rovers made a change and soon equalised, turning the game.",
        "evidence_ids": ["m061-s00126", "m064-s00134"]}]})
    use_models(ScriptedModelClient(standard=[english, ZH_DRAFT]))
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    assert pivot["narrative"]["headline"] == "换人之后流浪者掌控比赛" and pivot["narrative"]["verifier_attempts"] == 2


@pytest.mark.parametrize("params", [{"lang": "fr"}, {"audience": "coach"}, {"team": "middle"}, {"player": "nobody"}])
def test_bad_parameters_are_422(client, params):
    assert client.get(f"/api/pivots/{PIVOT_ID}", params=params).status_code == 422
    assert client.get(f"/api/matches/{DEMO_MATCH_ID}/pivots", params=params).status_code == 422


def test_unknown_pivot_is_still_404(client):
    assert client.get("/api/pivots/nope:p1", params={"lang": "zh"}).status_code == 404
