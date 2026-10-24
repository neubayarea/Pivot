// Agent traces for the S4 list. Today they come from the demo-1021 fixture; C03 swaps this for
// GET /api/matches/{id}/traces plus the `trace.appended` push, and the page stays the same.
import type { AgentTrace } from "@pivot/contracts";
import { DEMO_TRACES } from "../fixtures/traces-1021";

export type TraceChain = {
  chainId: string;
  pivotId: string;
  steps: AgentTrace[];
  /** Sum of step latencies: what pivot_publish_ms measures, minus queueing. */
  totalMs: number;
  outcome: "confirmed" | "degraded" | "rejected" | "running";
};

function outcomeOf(steps: AgentTrace[]): TraceChain["outcome"] {
  const last = steps[steps.length - 1];
  if (!last) return "running";
  if (last.agent === "template" || last.status === "degraded") return "degraded";
  if (last.agent === "judge" && last.status === "rejected") return "rejected";
  if (last.agent === "verifier" && last.status === "ok") return "confirmed";
  return "running";
}

export function groupChains(traces: AgentTrace[]): TraceChain[] {
  const byChain = new Map<string, AgentTrace[]>();
  for (const t of traces) byChain.set(t.chain_id, [...(byChain.get(t.chain_id) ?? []), t]);
  return [...byChain.entries()].map(([chainId, steps]) => {
    const sorted = steps.slice().sort((a, b) => a.step - b.step);
    const pivotId = sorted[0].input_ref.split(":").pop() ?? sorted[0].input_ref;
    return {
      chainId, pivotId, steps: sorted, outcome: outcomeOf(sorted),
      totalMs: sorted.reduce((sum, s) => sum + s.latency_ms, 0),
    };
  });
}

export function useTraceChains(): TraceChain[] {
  return groupChains(DEMO_TRACES).reverse();   // newest pivot first, like the S1 list
}
