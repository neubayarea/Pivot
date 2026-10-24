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


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("PIVOT_PROFILE", raising=False)
    monkeypatch.delenv("PIVOT_DEMO", raising=False)
    monkeypatch.delenv("PIVOT_PIPELINE", raising=False)
    with TestClient(app) as client:
        yield client


def use_models(models) -> Personalizer:
    app.state.personalizer = Personalizer(app.state.adapters.matches, models)
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
    models = ScriptedModelClient(standard=[ZH_DRAFT])
    use_models(models)
    first = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    second = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    listed = client.get(f"/api/matches/{DEMO_MATCH_ID}/pivots", params={"lang": "zh"}).json()[0]
    assert len(models.calls) == 1
    assert first == second == listed
    assert first["narrative"]["source"] == "llm" and first["narrative"]["headline"] == "换人之后流浪者掌控比赛"
    assert stored(ViewerPrefs(language="zh")).headline == "换人之后流浪者掌控比赛"


def test_rejected_draft_is_rewritten_with_the_verifier_feedback(client):
    bad = json.dumps({"headline": "坏稿", "sentences": [{"text": "流浪者换人。", "evidence_ids": ["nope"]}]},
                     ensure_ascii=False)
    models = ScriptedModelClient(standard=[bad, ZH_DRAFT])
    use_models(models)
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    assert pivot["narrative"]["source"] == "llm" and pivot["narrative"]["verifier_attempts"] == 2
    assert "The Verifier rejected your previous card" in models.calls[1][1][1]["content"]


def test_explainer_down_falls_back_to_the_template_in_that_language(client):
    use_models(ScriptedModelClient(standard=[ModelUnavailable("429")]))
    pivot = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh", "audience": "fan"}).json()
    assert pivot["prefs"]["language"] == "zh" and pivot["narrative"]["source"] == "template"


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


def test_new_run_of_the_pivot_drops_the_stored_versions(client):
    repo = app.state.adapters.matches
    models = ScriptedModelClient(standard=[ZH_DRAFT, ZH_DRAFT])
    use_models(models)
    client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"})
    pivot = asyncio.run(repo.get_pivot(DEMO_MATCH_ID, PIVOT_ID))
    asyncio.run(repo.upsert_pivot(pivot.model_copy(update={"chain_id": "c-demo-61-rerun"})))
    again = client.get(f"/api/pivots/{PIVOT_ID}", params={"lang": "zh"}).json()
    assert len(models.calls) == 2 and again["narrative"]["chain_id"] == "c-demo-61-rerun"


@pytest.mark.parametrize("params", [{"lang": "fr"}, {"audience": "coach"}, {"team": "middle"}, {"player": "nobody"}])
def test_bad_parameters_are_422(client, params):
    assert client.get(f"/api/pivots/{PIVOT_ID}", params=params).status_code == 422
    assert client.get(f"/api/matches/{DEMO_MATCH_ID}/pivots", params=params).status_code == 422


def test_unknown_pivot_is_still_404(client):
    assert client.get("/api/pivots/nope:p1", params={"lang": "zh"}).status_code == 404
