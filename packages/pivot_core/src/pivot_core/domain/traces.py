"""Verifier verdicts and agent traces, shown on the S4 trace panel."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import Model

AgentName = Literal[
    "judge", "explainer", "verifier", "template", "translator", "executor", "comparator", "recap",
]

IssueCode = Literal[
    "sentence_count", "too_long", "evidence_count", "evidence_invalid",
    "number_mismatch", "direction_mismatch", "significance_unsupported", "banned_term",
    "schema_invalid",
]


class VerifierIssue(Model):
    code: IssueCode
    message: str                              # fed back to the writer on a retry
    sentence_index: int | None = None


class Verdict(Model):
    passed: bool
    issues: list[VerifierIssue] = []


class AgentTrace(Model):
    trace_id: str                             # "{chain_id}:{step}"
    chain_id: str
    step: Annotated[int, Field(ge=0)]
    match_id: str
    agent: AgentName
    model: str | None = None                  # None for deterministic steps
    prompt_hash: str | None = None
    input_ref: str                            # pivot_id, scenario_id, ...
    output_summary: str
    latency_ms: Annotated[int, Field(ge=0)]
    tokens: Annotated[int, Field(ge=0)] = 0
    status: Literal["ok", "rejected", "retried", "degraded", "error"]
    verdict: Verdict | None = None            # verifier steps only
