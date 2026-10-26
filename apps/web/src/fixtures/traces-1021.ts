// Agent traces for the demo-1021 pivots, in the shape the worker writes (AgentTrace, D06).
// 38′ and 74′ pass the Verifier first time; 63′ is the demo moment: the Verifier rejects a
// number, the Explainer rewrites with the feedback, and the second draft passes. At 51′ the Judge
// looks at a candidate and turns it down, so it never becomes a pivot.
import type { AgentTrace } from "@pivot/contracts";
import { MATCH_ID } from "./demo-1021";

type StepSpec = Pick<AgentTrace, "agent" | "status" | "output_summary" | "latency_ms"> &
  Partial<Pick<AgentTrace, "model" | "tokens" | "prompt_hash" | "verdict">>;

const JUDGE_PROMPT = "3f9a1c07b2e4";
const EXPLAINER_PROMPT = "9c41e0d58a13";

function chain(pivotId: string, steps: StepSpec[]): AgentTrace[] {
  const chainId = `chain-${pivotId}`;
  return steps.map((s, step) => ({
    trace_id: `${chainId}:${step}`, chain_id: chainId, step, match_id: MATCH_ID, input_ref: pivotId,
    model: null, tokens: 0, prompt_hash: null, verdict: null, ...s,
  }));
}

const judge = (summary: string, latency: number): StepSpec => ({
  agent: "judge", status: "ok", output_summary: summary, latency_ms: latency,
  model: "pivot-mini", tokens: 1840, prompt_hash: JUDGE_PROMPT,
});
const explainer = (summary: string, latency: number, retry = false): StepSpec => ({
  agent: "explainer", status: retry ? "retried" : "ok", output_summary: summary, latency_ms: latency,
  model: "pivot-standard", tokens: retry ? 3420 : 3329, prompt_hash: EXPLAINER_PROMPT,
});
const pass = (latency: number): StepSpec => ({
  agent: "verifier", status: "ok", output_summary: "pass", latency_ms: latency, verdict: { passed: true, issues: [] },
});

export const DEMO_TRACES: AgentTrace[] = [
  ...chain("pv-38", [
    judge("is_pivot=true severity=3: the red card left Northvale a man down for the rest of the match.", 880),
    explainer("Red card tilted control to Harbour City", 3610),
    pass(36),
  ]),
  ...chain(`${MATCH_ID}:p51`, [
    { ...judge("is_pivot=false severity=1: one long ball, and the press was back within two minutes.", 760), status: "rejected" },
  ]),
  ...chain("pv-63", [
    judge("is_pivot=true severity=3: the substitution removed Harbour City's outlet on the left.", 910),
    explainer("Substitution flipped the left flank", 3820),
    {
      agent: "verifier", status: "rejected", output_summary: "number_mismatch", latency_ms: 41,
      verdict: {
        passed: false,
        issues: [{
          code: "number_mismatch", sentence_index: 0,
          message: "passes_final_third for home in 63-73 is 3, not 4.",
        }],
      },
    },
    explainer("Substitution flipped the left flank", 3110, true),
    pass(38),
  ]),
  ...chain("pv-74", [
    judge("is_pivot=true severity=2: the switch to a back three ended Northvale's pressing spell.", 840),
    explainer("Back three steadied Harbour City", 3240),
    pass(35),
  ]),
];
