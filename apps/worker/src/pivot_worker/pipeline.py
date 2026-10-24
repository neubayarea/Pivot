"""The Detect chain the worker runs for each candidate (Judge → Explainer ⇄ Verifier, architecture §6).

`Pipeline` is the seam for D06: the real Agent Framework workflow replaces `FakePipeline`
without touching the worker. A pipeline reports every agent step through `record`, which
the worker turns into an `AgentTrace`.
"""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Literal, Protocol

from pivot_core.domain import ExplanationSentence, Narrative, Pivot, PivotCandidate, Verdict, ViewerPrefs
from pivot_core.domain.traces import AgentName


@dataclass(frozen=True)
class Step:
    agent: AgentName
    output_summary: str
    status: Literal["ok", "rejected", "retried", "degraded", "error"] = "ok"
    model: str | None = None
    prompt_hash: str | None = None
    tokens: int = 0
    verdict: Verdict | None = None


class StepRecorder(Protocol):
    def __call__(self, step: Step) -> Awaitable[None]: ...


class Pipeline(Protocol):
    async def run(self, candidate: PivotCandidate, chain_id: str, record: StepRecorder) -> Pivot:
        """Judge the candidate and, if it holds, explain and verify it.

        Returns the pivot with a final status: confirmed, degraded (template text) or rejected.
        """
        ...


def pivot_id_of(candidate: PivotCandidate) -> str:
    return f"{candidate.match_id}:p{candidate.minute}"


class FakePipeline:
    """Stand-in until D06: always confirms the candidate with a fixed, verified narrative."""

    async def run(self, candidate: PivotCandidate, chain_id: str, record: StepRecorder) -> Pivot:
        swing = abs(candidate.swing)
        severity = 3 if swing >= 0.5 else 2 if swing >= 0.25 else 1
        await record(Step("judge", f"is_pivot=true severity={severity}", model="fake"))
        evidence = candidate.key_event_ids[:4] or [f"{candidate.match_id}:m{candidate.minute}"]
        narrative = Narrative(
            prefs=ViewerPrefs(),
            headline=f"Momentum swings to the {candidate.direction} side",
            sentences=[ExplanationSentence(
                text=f"The {candidate.direction} team took control of the game after these moments.",
                evidence_ids=evidence,
            )],
            source="llm",
            verifier_attempts=1,
            chain_id=chain_id,
        )
        await record(Step("explainer", narrative.headline, model="fake"))
        await record(Step("verifier", "pass", verdict=Verdict(passed=True)))
        return Pivot(
            pivot_id=pivot_id_of(candidate),
            match_id=candidate.match_id,
            minute=candidate.minute,
            direction=candidate.direction,
            severity=severity,
            status="confirmed",
            trigger_event_ids=candidate.key_event_ids,
            narrative=narrative,
            chain_id=chain_id,
        )
