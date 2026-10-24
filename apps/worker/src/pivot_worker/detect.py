"""DetectWorkflow: Judge → Explainer ⇄ Verifier → TemplateExplainer, on Agent Framework (D06, ADR-0004).

The graph is fixed (architecture §6.1):

    judge ──yes──> explainer ──> verifier ──pass──> confirmed
      │ no              ^            │ fail, fewer than 3 checks
      └──> rejected     └────────────┘
    any error in a node, the deadline, or the third check fails ──> template ──> degraded

It implements the worker's `Pipeline` seam, so the worker shell (A05) stores, traces and
pushes the result. Every node reports one `Step`, which becomes an `AgentTrace`.

A candidate always ends as a pivot: a node that hits any error records it under its own name
and hands over to the template, model calls share one `PIPELINE_DEADLINE`, and if the graph
itself fails or stalls, `DetectWorkflow.run` writes the template card directly.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler
from pydantic import ValidationError

from pivot_core.domain import (
    Match,
    MatchEvent,
    MinuteMetric,
    Narrative,
    Pivot,
    PivotCandidate,
    StatRef,
    Verdict,
    VerifierIssue,
    ViewerPrefs,
)
from pivot_core.ports import MatchRepository

from . import explainer, judge
from .context import ContextItem, from_match
from .models import ModelClient, ModelReply, ModelUnavailable, Tier
from .pipeline import Step, StepRecorder
from .template import template_explain
from .verifier import StatSource, verify

MAX_CHECKS = 3                                # first draft plus two rewrites
JUDGE_TIMEOUT, EXPLAINER_TIMEOUT = 4.0, 8.0   # per model attempt
PIPELINE_DEADLINE = 20.0                      # all model calls of one candidate, retries included
GRACE_SECONDS = 5.0                           # on top of the deadline before the graph is given up


class NoStats:
    """Until B05's StatCalculator lands: nothing can be recomputed, so numbers are rejected."""

    def compute(self, ref: StatRef) -> float:
        raise LookupError("StatCalculator is not available yet (B05)")


StatsFactory = Callable[[Match | None, list[MatchEvent], list[MinuteMetric]], StatSource]


@dataclass
class MatchView:
    events: dict[str, MatchEvent]
    metrics: list[MinuteMetric]
    stats: StatSource
    team_names: dict[str, str]
    player_names: dict[str, str] = field(default_factory=dict)
    context: list[ContextItem] = field(default_factory=list)


async def load_view(repo: MatchRepository, match_id: str, stats_factory: StatsFactory | None = None) -> MatchView:
    match = await repo.get_match(match_id)
    events = await repo.list_events(match_id)
    metrics = await repo.list_metrics(match_id)
    names = {"home": match.home.name, "away": match.away.name} if match else {"home": "Home", "away": "Away"}
    players = {p.player_id: p.name for t in (match.home, match.away) for p in t.squad} if match else {}
    return MatchView(events={e.event_id: e for e in events}, metrics=metrics,
                     stats=stats_factory(match, events, metrics) if stats_factory else NoStats(),
                     team_names=names, player_names=players, context=from_match(match) if match else [])


@dataclass(frozen=True)
class Run:
    """Workflow state, handed from node to node.

    Frozen on purpose: Agent Framework evaluates edge conditions when it delivers a message,
    so a node must send a new `Run` (dataclasses.replace) rather than change the one it got.
    """

    candidate: PivotCandidate
    chain_id: str
    record: StepRecorder
    view: MatchView
    prefs: ViewerPrefs = field(default_factory=ViewerPrefs)
    next: str = "explain"
    verdict: judge.JudgeVerdict | None = None
    status: str = "confirmed"
    checks: int = 0
    draft: Narrative | None = None
    feedback: Verdict | None = None
    reply: str | None = None                  # the Explainer's last raw answer, shown to it on a rewrite
    schema_error: str | None = None
    deadline: float = math.inf                # time.monotonic() by which model calls must be done

    def __deepcopy__(self, memo: dict) -> Run:
        # Agent Framework deep-copies every message into its "executor invoked" event. A Run is
        # frozen and holds the recorder (and through it the worker's adapters), so share it as is.
        return self

    def pivot(self, status: str, narrative: Narrative | None) -> Pivot:
        p = judge.make_pivot(self.candidate, self.verdict, chain_id=self.chain_id, status=status)
        return p.model_copy(update={"narrative": narrative})

    async def ask(self, models: ModelClient, tier: Tier, messages: list[dict[str, str]],
                  per_try: float) -> ModelReply:
        """One model call, cut short when the chain's deadline comes first."""
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise ModelUnavailable("pipeline deadline passed")
        async with asyncio.timeout(left):
            return await models.complete_json(tier, messages, timeout=min(per_try, left))


def _why(e: Exception) -> str:
    return f"{type(e).__name__}: {e}" if str(e) else type(e).__name__


def template_pivot(r: Run) -> tuple[Pivot, Narrative]:
    v = r.view
    narrative = template_explain(r.candidate, events=v.events, stats=v.stats, team_names=v.team_names,
                                 prefs=r.prefs, chain_id=r.chain_id, verifier_attempts=r.checks,
                                 context=explainer.shown_context(r.candidate, v.events, v.context))
    return r.pivot("degraded", narrative), narrative


def with_computed(narrative: Narrative, stats: StatSource) -> Narrative:
    """On-screen numbers always come from the StatCalculator, not from the model (ADR-0005)."""
    sentences = [s.model_copy(update={"claims": [c.model_copy(update={"value": stats.compute(c.stat_ref)})
                                                 for c in s.claims]}) for s in narrative.sentences]
    return narrative.model_copy(update={"sentences": sentences})


class JudgeNode(Executor):
    def __init__(self, models: ModelClient) -> None:
        super().__init__(id="judge")
        self.models = models

    @handler
    async def run(self, r: Run, ctx: WorkflowContext[Run, Pivot]) -> None:
        v = r.view
        prompt, messages = judge.build_messages(r.candidate, events=v.events, metrics=v.metrics, stats=v.stats,
                                                team_names=v.team_names)
        try:
            reply = await r.ask(self.models, "mini", messages, JUDGE_TIMEOUT)
            shown = {ev.event_id for ev in judge.judge_events(r.candidate, v.events)}
            verdict = judge.parse_verdict(reply.text, r.candidate, shown)
        except Exception as e:                   # includes ValidationError and judge.InvalidVerdict
            await r.record(Step("judge", f"unavailable ({_why(e)}); detector only"[:200], "degraded",
                                prompt_hash=prompt.hash))
            await ctx.send_message(replace(r, verdict=judge.fallback_verdict(r.candidate), status="degraded",
                                           next="template"))
            return
        summary = f"is_pivot={str(verdict.is_pivot).lower()} severity={verdict.severity}: {verdict.reason}"
        r = replace(r, verdict=verdict)
        if not verdict.is_pivot:
            await r.record(Step("judge", summary, "rejected", reply.model, prompt.hash, reply.tokens))
            await ctx.yield_output(r.pivot("rejected", None))
            return
        await r.record(Step("judge", summary, "ok", reply.model, prompt.hash, reply.tokens))
        await ctx.send_message(replace(r, next="explain"))


class ExplainerNode(Executor):
    def __init__(self, models: ModelClient) -> None:
        super().__init__(id="explainer")
        self.models = models

    @handler
    async def run(self, r: Run, ctx: WorkflowContext[Run]) -> None:
        v = r.view
        prompt, messages = explainer.build_messages(
            r.candidate, events=v.events, stats=v.stats, team_names=v.team_names, prefs=r.prefs,
            player_names=v.player_names, context=v.context, feedback=r.feedback, previous=r.reply)
        status = "retried" if r.checks else "ok"
        try:
            reply = await r.ask(self.models, "standard", messages, EXPLAINER_TIMEOUT)
        except Exception as e:
            await r.record(Step("explainer", f"unavailable: {_why(e)}"[:200], "error", prompt_hash=prompt.hash))
            await ctx.send_message(replace(r, next="template"))
            return
        try:
            draft, error = explainer.parse_draft(reply.text, prefs=r.prefs, chain_id=r.chain_id), None
            summary = draft.headline
        except ValidationError as e:
            draft, error = None, f"{e.error_count()} schema errors: {e.errors()[0]['msg']}"
            summary = f"invalid output ({error})"
        except Exception as e:
            draft, error = None, _why(e)[:200]
            summary = f"invalid output ({error})"
        await r.record(Step("explainer", summary, status, reply.model, prompt.hash, reply.tokens))
        await ctx.send_message(replace(r, draft=draft, reply=reply.text, schema_error=error, next="verify"))


class VerifierNode(Executor):
    def __init__(self) -> None:
        super().__init__(id="verifier")

    @handler
    async def run(self, r: Run, ctx: WorkflowContext[Run, Pivot]) -> None:
        r = replace(r, checks=r.checks + 1)
        try:
            if r.draft is None:
                verdict = Verdict(passed=False,
                                  issues=[VerifierIssue(code="schema_invalid", message=r.schema_error or "")])
            else:
                v = r.view
                verdict = verify(r.draft, pivot_minute=r.candidate.minute, events=v.events, stats=v.stats,
                                 context=explainer.shown_context(r.candidate, v.events, v.context),
                                 team_names=v.team_names)
            narrative = None
            if verdict.passed:
                narrative = with_computed(r.draft, r.view.stats).model_copy(update={"verifier_attempts": r.checks})
        except Exception as e:                   # e.g. a bug in the stat source: rewriting cannot fix it
            await r.record(Step("verifier", f"error: {_why(e)}"[:200], "error"))
            await ctx.send_message(replace(r, next="template"))
            return
        summary = "pass" if verdict.passed else "; ".join(i.code for i in verdict.issues)
        await r.record(Step("verifier", summary, "ok" if verdict.passed else "rejected", verdict=verdict))
        if narrative is not None:
            await ctx.yield_output(r.pivot(r.status, narrative))
            return
        await ctx.send_message(replace(r, feedback=verdict, next="explain" if r.checks < MAX_CHECKS else "template"))


class TemplateNode(Executor):
    def __init__(self) -> None:
        super().__init__(id="template")

    @handler
    async def run(self, r: Run, ctx: WorkflowContext[Run, Pivot]) -> None:
        pivot, narrative = template_pivot(r)
        await r.record(Step("template", narrative.headline, "degraded"))
        await ctx.yield_output(pivot)


def _to(target: str) -> Callable[[Run], bool]:
    return lambda r: r.next == target


class DetectWorkflow:
    """The worker's `Pipeline`: builds the Agent Framework graph and runs one candidate through it."""

    def __init__(self, repo: MatchRepository, models: ModelClient, stats_factory: StatsFactory | None = None,
                 prefs: ViewerPrefs | None = None, deadline: float = PIPELINE_DEADLINE) -> None:
        self.repo, self.models, self.stats_factory = repo, models, stats_factory
        self.prefs = prefs or ViewerPrefs()
        self.deadline = deadline

    def build(self):
        j, e, v, t = JudgeNode(self.models), ExplainerNode(self.models), VerifierNode(), TemplateNode()
        return (WorkflowBuilder(start_executor=j, name="detect")
                .add_edge(j, e, condition=_to("explain")).add_edge(j, t, condition=_to("template"))
                .add_edge(e, v, condition=_to("verify")).add_edge(e, t, condition=_to("template"))
                .add_edge(v, e, condition=_to("explain")).add_edge(v, t, condition=_to("template"))
                .build())

    async def run(self, candidate: PivotCandidate, chain_id: str, record: StepRecorder) -> Pivot:
        # A failure to read the match is the store's problem: let the worker retry the message.
        view = await load_view(self.repo, candidate.match_id, self.stats_factory)
        run = Run(candidate, chain_id, record, view, self.prefs, deadline=time.monotonic() + self.deadline)
        try:
            async with asyncio.timeout(self.deadline + GRACE_SECONDS):
                result = await self.build().run(run)
            outputs = result.get_outputs()
            if outputs:
                return outputs[-1]
            why = f"no pivot ({result.get_final_state()})"
        except Exception as e:
            why = _why(e)
        # Last resort: the graph failed or stalled, so the template card is written here.
        pivot, _ = template_pivot(replace(run, verdict=judge.fallback_verdict(candidate)))
        await record(Step("template", f"workflow failed ({why}); template card"[:200], "degraded"))
        return pivot
