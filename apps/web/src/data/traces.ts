// Agent traces for the S4 list (US-08), from `GET /api/matches/{id}/traces` or
// `GET /api/pivots/{id}/traces` (Ax4), or the demo-1021 fixture when the page runs on `?fixture=1`.
// Only the detect chains (Judge → Explainer ⇄ Verifier → template) are listed here; What-if runs
// have their own chains and their own page.
import { useEffect, useState } from "react";
import type { AgentTrace, VerifierIssue } from "@pivot/contracts";
import { DEMO_TRACES } from "../fixtures/traces-1021";
import { ApiError, api } from "./live/api";

export type TraceChain = {
  chainId: string;
  /** The pivot (or the candidate the Judge turned down): `input_ref`, compared whole, never split. */
  pivotId: string;
  steps: AgentTrace[];
  /** Sum of step latencies: what pivot_publish_ms measures, minus queueing. */
  totalMs: number;
  outcome: "confirmed" | "degraded" | "rejected" | "running";
  /** Explainer drafts after the first: each one answers a Verifier rejection. */
  rewrites: number;
  /** Every issue the Verifier sent back, in order. */
  rejections: VerifierIssue[];
  /** The rule-based template wrote the final text because no draft passed. */
  template: boolean;
};

const DETECT = new Set<AgentTrace["agent"]>(["judge", "explainer", "verifier", "template", "translator"]);

function outcomeOf(steps: AgentTrace[]): TraceChain["outcome"] {
  const last = steps[steps.length - 1];
  if (!last) return "running";
  if (last.agent === "template" || last.status === "degraded") return "degraded";
  if (last.agent === "judge" && last.status === "rejected") return "rejected";
  if (last.agent === "verifier" && last.status === "ok") return "confirmed";
  return "running";
}

/** Detect chains, steps in order, newest candidate first like the S1 list. */
export function groupChains(traces: AgentTrace[]): TraceChain[] {
  const byChain = new Map<string, AgentTrace[]>();
  for (const t of traces) byChain.set(t.chain_id, [...(byChain.get(t.chain_id) ?? []), t]);
  const chains = [...byChain.entries()]
    .filter(([, steps]) => steps.every((s) => DETECT.has(s.agent)))
    .map(([chainId, steps]): TraceChain => {
      const sorted = steps.slice().sort((a, b) => a.step - b.step);
      return {
        chainId, pivotId: sorted[0].input_ref, steps: sorted, outcome: outcomeOf(sorted),
        totalMs: sorted.reduce((sum, s) => sum + s.latency_ms, 0),
        rewrites: Math.max(0, sorted.filter((s) => s.agent === "explainer").length - 1),
        rejections: sorted.flatMap((s) => (s.agent === "verifier" && s.verdict && !s.verdict.passed ? s.verdict.issues : [])),
        template: sorted.some((s) => s.agent === "template"),
      };
    });
  return chains.sort((a, b) => (refMinute(b.pivotId) ?? -1) - (refMinute(a.pivotId) ?? -1));
}

/** The elapsed minute in an id like `M-seed-29:p39`, for candidates with no pivot to read it from. */
export function refMinute(ref: string): number | null {
  const m = /:p(\d+)$/.exec(ref);
  return m ? Number(m[1]) : null;
}

export type TraceSource = {
  match: (matchId: string) => Promise<AgentTrace[]>;
  pivot: (pivotId: string) => Promise<AgentTrace[]>;
};

export const liveTraceSource: TraceSource = {
  match: api.listMatchTraces,
  // 404: the API has no pivot and no record under that id; the page says so instead of failing.
  pivot: (id) => api.listPivotTraces(id).catch((e) => (e instanceof ApiError && e.status === 404 ? [] : Promise.reject(e))),
};

export const fixtureTraceSource: TraceSource = {
  match: async () => DEMO_TRACES,
  pivot: async (id) => DEMO_TRACES.filter((t) => t.input_ref === id),
};

export type TraceState = { kind: "loading" } | { kind: "error"; error: unknown } | { kind: "ready"; chains: TraceChain[] };

/**
 * One pivot's chains, or the whole match's. `version` changes when the match has news (a pivot
 * appears or settles), so the list is fetched again and the new steps show up.
 */
export function useTraceChains(source: TraceSource, matchId: string, pivotId: string | undefined, version: string, reload = 0) {
  const [state, setState] = useState<TraceState>({ kind: "loading" });
  const target = pivotId ?? matchId;
  // A refresh keeps the list on screen; only a different match or pivot shows the loading state.
  useEffect(() => setState({ kind: "loading" }), [target, reload]);
  useEffect(() => {
    let alive = true;
    (pivotId ? source.pivot(pivotId) : source.match(matchId)).then(
      (traces) => alive && setState({ kind: "ready", chains: groupChains(traces) }),
      (error) => alive && setState((s) => (s.kind === "ready" ? s : { kind: "error", error })),
    );
    return () => {
      alive = false;
    };
  }, [source, matchId, pivotId, version, reload]);
  return state;
}
