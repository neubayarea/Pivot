import asyncio
import json
import time

import pytest
from azure.core.exceptions import ClientAuthenticationError

from pivot_adapters import build_adapters
from pivot_core.domain import PivotCandidate
from pivot_core.ports import PIVOT_CANDIDATES
from pivot_worker import detect
from pivot_worker.detect import DetectWorkflow, NoStats
from pivot_worker.models import ModelUnavailable, ScriptedModelClient
from pivot_worker.testing import claim
from pivot_worker.worker import Worker

CANDIDATE = PivotCandidate(match_id="M-test", minute=63, direction="home", cusum_stat=4.2, swing=0.3,
                           key_event_ids=["m063-s01042"], window=(58, 68))
YES = json.dumps({"is_pivot": True, "severity": 2, "trigger_event_ids": ["m063-s01042"], "reason": "sub opened it"})
NO = json.dumps({"is_pivot": False, "severity": 1, "trigger_event_ids": [], "reason": "noise"})


def draft(value):
    """A card whose second claim is `value`; the real value is 9."""
    return json.dumps({"headline": "Okafor's arrival flips the left flank", "sentences": [{
        "text": f"Final-third passes rose from 3 to {value} after the change.", "evidence_ids": ["m063-s01042"],
        "claims": [claim("passes_final_third", "home", (56, 61), 3).model_dump(),
                   claim("passes_final_third", "home", (61, 66), value).model_dump()]}]})


def run(events, stats, models, candidate=CANDIDATE):
    adapters = build_adapters("local")
    asyncio.run(adapters.matches.append_events(list(events.values())))
    steps = []

    async def record(step):
        steps.append(step)

    workflow = DetectWorkflow(adapters.matches, models, stats_factory=lambda m, e, x: stats)
    pivot = asyncio.run(workflow.run(candidate, "chain-1", record))
    return pivot, [(s.agent, s.status) for s in steps]


def test_first_draft_passes(events, stats):
    pivot, steps = run(events, stats, ScriptedModelClient(standard=[draft(9)], mini=[YES]))
    assert pivot.status == "confirmed" and pivot.severity == 2 and pivot.narrative.verifier_attempts == 1
    assert steps == [("judge", "ok"), ("explainer", "ok"), ("verifier", "ok")]


def test_rejected_then_rewritten_then_passed(events, stats):
    models = ScriptedModelClient(standard=[draft(12), draft(9)], mini=[YES])
    pivot, steps = run(events, stats, models)
    assert pivot.status == "confirmed" and pivot.narrative.verifier_attempts == 2
    assert steps == [("judge", "ok"), ("explainer", "ok"), ("verifier", "rejected"),
                     ("explainer", "retried"), ("verifier", "ok")]
    retry_request = models.calls[2][1][1]["content"]
    assert "The Verifier rejected your previous card" in retry_request and "is 9, not 12" in retry_request


def test_two_rewrites_then_the_template(events, stats):
    pivot, steps = run(events, stats, ScriptedModelClient(standard=[draft(12)] * 3, mini=[YES]))
    assert pivot.status == "degraded" and pivot.narrative.source == "template"
    assert pivot.narrative.verifier_attempts == 3
    assert steps == [("judge", "ok")] + [("explainer", "ok"), ("verifier", "rejected")] + \
        [("explainer", "retried"), ("verifier", "rejected")] * 2 + [("template", "degraded")]


def test_invalid_json_counts_as_a_failed_check(events, stats):
    pivot, steps = run(events, stats, ScriptedModelClient(standard=['{"headline": 1}', draft(9)], mini=[YES]))
    assert pivot.status == "confirmed" and steps[2] == ("verifier", "rejected")


def test_judge_says_no(events, stats):
    models = ScriptedModelClient(mini=[NO])
    pivot, steps = run(events, stats, models)
    assert pivot.status == "rejected" and pivot.narrative is None and pivot.trigger_event_ids == []
    assert steps == [("judge", "rejected")] and all(tier == "mini" for tier, _ in models.calls)


@pytest.mark.parametrize("mini,standard,expected", [
    ([ModelUnavailable("429")], [], [("judge", "degraded"), ("template", "degraded")]),
    ([YES], [ModelUnavailable("timeout")], [("judge", "ok"), ("explainer", "error"), ("template", "degraded")]),
])
def test_unavailable_models_degrade_to_the_template(events, stats, mini, standard, expected):
    pivot, steps = run(events, stats, ScriptedModelClient(standard=standard, mini=mini))
    assert pivot.status == "degraded" and pivot.narrative.source == "template" and steps == expected


def test_screen_numbers_are_the_recomputed_values(events, stats):
    text = json.dumps({"headline": "Rovers tidy up", "sentences": [{
        "text": "Pass accuracy reached 68% after the change.", "evidence_ids": ["m063-s01042"],
        "claims": [claim("pass_accuracy_pct", "home", (61, 66), 68).model_dump()]}]})
    pivot, _ = run(events, stats, ScriptedModelClient(standard=[text], mini=[YES]))
    assert pivot.narrative.sentences[0].claims[0].value == 68.4


def test_without_a_stat_calculator_numbers_are_rejected_and_the_template_takes_over(events):
    pivot, steps = run(events, NoStats(), ScriptedModelClient(standard=[draft(9)] * 3, mini=[YES]))
    assert pivot.status == "degraded" and steps[-1] == ("template", "degraded")


def test_inside_the_worker_shell(events, stats):
    adapters = build_adapters("local")
    models = ScriptedModelClient(standard=[draft(12), draft(9)], mini=[YES])
    worker = Worker(adapters, DetectWorkflow(adapters.matches, models, stats_factory=lambda m, e, x: stats))

    async def go():
        await adapters.matches.append_events(list(events.values()))
        await adapters.queue.send(PIVOT_CANDIDATES, "M-test:63", CANDIDATE.model_dump(mode="json", round_trip=True))
        await worker.run_once(timeout=1)
        return await adapters.matches.get_pivot("M-test", "M-test:p63"), await adapters.traces.list_traces("M-test")

    pivot, traces = asyncio.run(go())
    assert pivot.status == "confirmed"
    assert [(t.agent, t.status) for t in traces] == [("judge", "ok"), ("explainer", "ok"), ("verifier", "rejected"),
                                                    ("explainer", "retried"), ("verifier", "ok")]
    assert [t.step for t in traces] == [0, 1, 2, 3, 4]
    assert traces[2].verdict.issues[0].code == "number_mismatch" and traces[1].prompt_hash


AUTH = ClientAuthenticationError("bad client secret")
SERVER = RuntimeError("Error code: 500 - internal server error")
BAD_REQUEST = ValueError("Error code: 400 - content filter")


@pytest.mark.parametrize("error", [AUTH, SERVER, BAD_REQUEST, KeyError("deployment")])
def test_any_judge_error_degrades_to_the_template(events, stats, error):
    pivot, steps = run(events, stats, ScriptedModelClient(mini=[error]))
    assert pivot.status == "degraded" and pivot.narrative.source == "template"
    assert steps == [("judge", "degraded"), ("template", "degraded")]


@pytest.mark.parametrize("error", [AUTH, SERVER, BAD_REQUEST, KeyError("deployment")])
def test_any_explainer_error_degrades_to_the_template(events, stats, error):
    pivot, steps = run(events, stats, ScriptedModelClient(standard=[error], mini=[YES]))
    assert pivot.status == "degraded" and pivot.narrative.source == "template"
    assert steps == [("judge", "ok"), ("explainer", "error"), ("template", "degraded")]


def test_a_verifier_error_degrades_to_the_template(events, stats, monkeypatch):
    def broken(narrative, stats):
        raise ZeroDivisionError("stat calculator blew up")

    monkeypatch.setattr(detect, "with_computed", broken)
    pivot, steps = run(events, stats, ScriptedModelClient(standard=[draft(9)], mini=[YES]))
    assert pivot.status == "degraded" and pivot.narrative.source == "template"
    assert steps == [("judge", "ok"), ("explainer", "ok"), ("verifier", "error"), ("template", "degraded")]


class SlowModels(ScriptedModelClient):
    async def complete_json(self, tier, messages, *, timeout):
        self.calls.append((tier, timeout))
        await asyncio.sleep(timeout)
        raise ModelUnavailable("timed out")


def test_the_deadline_bounds_the_whole_chain(events, stats):
    adapters = build_adapters("local")
    models = SlowModels()
    steps = []

    async def record(step):
        steps.append((step.agent, step.status))

    async def go():
        await adapters.matches.append_events(list(events.values()))
        return await DetectWorkflow(adapters.matches, models, lambda m, e, x: stats, deadline=0.3).run(
            CANDIDATE, "chain-1", record)

    started = time.monotonic()
    pivot = asyncio.run(go())
    assert time.monotonic() - started < 1.0
    assert pivot.status == "degraded" and steps == [("judge", "degraded"), ("template", "degraded")]
    assert models.calls[0][1] <= 0.3                     # the per-try timeout shrinks to what is left


def test_if_the_graph_itself_fails_the_template_is_written_anyway(events, stats, monkeypatch):
    class Broken:
        async def run(self, message):
            raise RuntimeError("workflow engine crashed")

    monkeypatch.setattr(DetectWorkflow, "build", lambda self: Broken())
    pivot, steps = run(events, stats, ScriptedModelClient())
    assert pivot.status == "degraded" and pivot.narrative.source == "template"
    assert steps == [("template", "degraded")]


def test_explainer_errors_are_traced_under_the_explainer_and_the_message_completes(events, stats):
    adapters = build_adapters("local")
    models = ScriptedModelClient(standard=[AUTH], mini=[YES])
    worker = Worker(adapters, DetectWorkflow(adapters.matches, models, stats_factory=lambda m, e, x: stats))

    async def go():
        await adapters.matches.append_events(list(events.values()))
        await adapters.queue.send(PIVOT_CANDIDATES, "M-test:63", CANDIDATE.model_dump(mode="json", round_trip=True))
        await worker.run_once(timeout=1)
        left = await adapters.queue.receive(PIVOT_CANDIDATES, timeout=0.1)
        return await adapters.matches.get_pivot("M-test", "M-test:p63"), await adapters.traces.list_traces("M-test"), left

    pivot, traces, left = asyncio.run(go())
    assert pivot.status == "degraded" and left is None
    assert [(t.agent, t.status) for t in traces] == [("judge", "ok"), ("explainer", "error"), ("template", "degraded")]
    assert "ClientAuthenticationError" in traces[1].output_summary
