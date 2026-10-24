import asyncio

import pytest
from fastapi.testclient import TestClient

from pivot_api.app import app
from pivot_api.demo import DEMO_MATCH_ID, demo_traces
from pivot_core.domain import AgentTrace

P = f"{DEMO_MATCH_ID}:p"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("PIVOT_PROFILE", raising=False)
    monkeypatch.delenv("PIVOT_DEMO", raising=False)
    with TestClient(app) as client:
        yield client


def _trace(chain_id: str, step: int, input_ref: str, **kw) -> AgentTrace:
    return AgentTrace(trace_id=f"{chain_id}:{step}", chain_id=chain_id, step=step, match_id=DEMO_MATCH_ID,
                      agent=kw.pop("agent", "judge"), input_ref=input_ref, output_summary="x", latency_ms=1,
                      status=kw.pop("status", "ok"), **kw)


def _append(client, *traces: AgentTrace) -> None:
    async def run():
        for t in traces:
            await app.state.adapters.traces.append_trace(t)
    asyncio.run(run())


def _chains(traces: list[dict]) -> list[tuple[str, list[int]]]:
    out: list[tuple[str, list[int]]] = []
    for t in traces:
        if not out or out[-1][0] != t["chain_id"]:
            out.append((t["chain_id"], []))
        out[-1][1].append(t["step"])
    return out


def test_match_traces_are_grouped_by_chain_in_step_order(client):
    traces = client.get(f"/api/matches/{DEMO_MATCH_ID}/traces").json()
    assert _chains(traces) == [("c-demo-38", [0]), ("c-demo-61", [0, 1, 2, 3, 4]), ("c-demo-71", list(range(8)))]
    assert len(traces) == len(demo_traces())


def test_traces_appended_out_of_order_come_back_sorted(client):
    _append(client, _trace("detect:x:d2", 1, f"{P}50", agent="explainer"), _trace("detect:x:d1", 0, f"{P}50"),
            _trace("detect:x:d2", 0, f"{P}50"))
    traces = client.get(f"/api/pivots/{P}50/traces").json()
    assert _chains(traces) == [("detect:x:d1", [0]), ("detect:x:d2", [0, 1])]


def test_pivot_traces_show_the_rewrite_then_the_publish(client):
    traces = client.get(f"/api/pivots/{P}61/traces").json()
    assert {t["input_ref"] for t in traces} == {f"{P}61"}
    assert [(t["agent"], t["status"]) for t in traces] == [
        ("judge", "ok"), ("explainer", "ok"), ("verifier", "rejected"), ("explainer", "retried"), ("verifier", "ok")]
    assert traces[2]["verdict"]["issues"][0]["code"] == "number_mismatch"
    assert traces[0]["trace_id"] == "c-demo-61:0"


def test_pivot_traces_show_the_template_fallback(client):
    traces = client.get(f"/api/pivots/{P}71/traces").json()
    assert [t["status"] for t in traces if t["agent"] == "verifier"] == ["rejected"] * 3
    assert (traces[-1]["agent"], traces[-1]["status"]) == ("template", "degraded")


def test_a_candidate_judged_not_a_pivot_is_found_by_its_id(client):
    assert client.get(f"/api/pivots/{P}38").status_code == 404           # no pivot stored for it...
    traces = client.get(f"/api/pivots/{P}38/traces").json()             # ...but its chain is here
    assert [(t["agent"], t["status"]) for t in traces] == [("judge", "rejected")]


def test_input_ref_is_matched_on_the_full_pivot_id(client):
    # Ids that a split(":").pop() or prefix match would confuse with p61.
    _append(client, _trace("other", 0, "other-match:p61"), _trace("p610", 0, f"{P}610"),
            _trace("bare", 0, "p61"))
    traces = client.get(f"/api/pivots/{P}61/traces").json()
    assert {t["chain_id"] for t in traces} == {"c-demo-61"}


def test_a_stored_pivot_without_traces_is_an_empty_list(client):
    async def run():
        p61 = await app.state.adapters.matches.get_pivot(DEMO_MATCH_ID, f"{P}61")
        await app.state.adapters.matches.upsert_pivot(p61.model_copy(update={"pivot_id": f"{P}62", "minute": 62}))
    asyncio.run(run())
    response = client.get(f"/api/pivots/{P}62/traces")
    assert (response.status_code, response.json()) == (200, [])


def test_unknown_match_or_pivot_is_404(client):
    assert client.get("/api/matches/nope/traces").status_code == 404
    assert client.get(f"/api/pivots/{P}99/traces").status_code == 404
    assert client.get("/api/pivots/nope:p61/traces").status_code == 404
    assert client.get("/api/pivots/no-separator/traces").status_code == 404
