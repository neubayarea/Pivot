"""Ax29 (#201): the pipeline the deployed process builds gets a real stat sheet from the StatCalculator.

Before, `build_pipeline` and `personalizer_from_env` passed no `stats_factory`, so the Explainer saw an
empty sheet and the Verifier rejected every number. Here the recorded match (eval/fixtures/demo-1021.json)
goes through the same composition root as `pivot_api.single`, with a model that copies two numbers from the sheet: the
card passes only if the Verifier recomputes them from the same StatCalculator.
"""

import asyncio
import json

from pivot_adapters import build_adapters
from pivot_api import personalize, sims
from pivot_worker import __main__ as worker_main
from pivot_worker.detect import match_stats
from pivot_worker.models import ModelReply
from pivot_worker.worker import Worker


class SheetModel:
    """Judge: yes. Explainer: one sentence quoting the attacking side's passes before and after."""

    def __init__(self) -> None:
        self.sheets: list[list[dict]] = []

    async def complete_json(self, tier, messages, *, timeout):
        request, _ = json.JSONDecoder().raw_decode(messages[-1]["content"])
        key = request.get("alarm", request.get("pivot"))["key_event_ids"]
        evidence = [e["id"] for e in request["events"] if e["id"] in key][:1] or [request["events"][0]["id"]]
        if tier == "mini":
            reply = {"is_pivot": True, "severity": 2, "trigger_event_ids": evidence, "reason": "momentum swung"}
        else:
            sheet = request["stat_sheet"]
            self.sheets.append(sheet)
            team = next(side for side, name in request["teams"].items() if name == request["pivot"]["towards"])
            before, after = sorted((c for c in sheet if c["stat_ref"]["metric"] == "passes"
                                    and c["stat_ref"]["team"] == team and c["stat_ref"]["player_id"] is None),
                                   key=lambda c: c["stat_ref"]["window"][0])
            reply = {"headline": "The passing picks up",
                     "sentences": [{"text": f"Passes went from {before['value']:g} to {after['value']:g}.",
                                    "evidence_ids": evidence, "claims": [before, after]}]}
        return ModelReply(text=json.dumps(reply), model=f"sheet-{tier}", tokens=10)


def test_deployed_pipeline_writes_verified_numbers_from_the_stat_sheet(monkeypatch):
    model = SheetModel()
    monkeypatch.setenv("PIVOT_PIPELINE", "detect")
    monkeypatch.setattr(worker_main, "model_client_from_env", lambda: model)

    async def run():
        adapters = build_adapters("local")
        match_id, _ = await sims.load_fixture(adapters, sims.FIXTURE)
        worker = Worker(adapters, worker_main.build_pipeline(adapters))
        while await worker.run_once(timeout=0.01):
            pass
        return await adapters.matches.list_pivots(match_id)

    pivots = asyncio.run(run())
    assert model.sheets and all(len(sheet) > 20 for sheet in model.sheets)
    metrics = {c["stat_ref"]["metric"] for c in model.sheets[0]}
    assert {"passes", "shots", "xg", "pressures", "momentum_avg"} <= metrics
    with_numbers = [p for p in pivots if p.status == "confirmed" and p.narrative.sentences[0].claims]
    candidates = {c["minute"] for c in json.loads(sims.FIXTURE.read_text(encoding="utf-8"))["candidates"]}
    assert with_numbers and {p.minute for p in with_numbers} <= candidates


def test_personalizer_from_env_uses_the_stat_calculator(monkeypatch):
    monkeypatch.setenv("PIVOT_PIPELINE", "detect")
    monkeypatch.setattr(personalize, "model_client_from_env", lambda: SheetModel())
    assert personalize.personalizer_from_env(build_adapters("local").matches).stats_factory is match_stats
