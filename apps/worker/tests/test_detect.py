import asyncio
import json

import pytest

from pivot_adapters import build_adapters
from pivot_core.domain import PivotCandidate
from pivot_core.ports import PIVOT_CANDIDATES
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
    assert f"Your previous card:\n{draft(12)}" in retry_request


def test_invalid_json_is_shown_back_on_the_rewrite(events, stats):
    models = ScriptedModelClient(standard=['{"headline": 1}', draft(9)], mini=[YES])
    run(events, stats, models)
    assert 'Your previous card:\n{"headline": 1}' in models.calls[2][1][1]["content"]


@pytest.mark.parametrize("triggers", [["made-up"], ["m063-s00100"]])     # invented, or outside the window
def test_a_yes_without_a_real_trigger_is_not_confirmed(events, stats, triggers):
    yes = json.dumps({"is_pivot": True, "severity": 2, "trigger_event_ids": triggers, "reason": "trust me"})
    pivot, steps = run(events, stats, ScriptedModelClient(mini=[yes]))
    assert pivot.status == "degraded" and steps == [("judge", "degraded"), ("template", "degraded")]
    assert pivot.trigger_event_ids == ["m063-s01042"]


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
