import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import type { AgentTrace } from "@pivot/contracts";
import Card from "../components/Card";
import Kicker from "../components/Kicker";
import Stamp from "../components/Stamp";
import { useMatch } from "../data/match";
import { useTraceChains, type TraceChain } from "../data/traces";
import "../styles/traces.css";

// S4 · Agent trace (US-08). One card per detect chain, one row per agent handoff; a rejected
// check shows what the writer wrote and what the Verifier recomputed. Rows open for details.

const AGENT: Record<AgentTrace["agent"], string> = {
  judge: "PivotJudge", explainer: "Explainer", verifier: "Verifier", template: "TemplateExplainer",
  translator: "Translator", executor: "Executor", comparator: "Comparator", recap: "Recap",
};

const OUTCOME: Record<TraceChain["outcome"], ReactNode> = {
  confirmed: <Stamp tone="ok">Verified</Stamp>,
  degraded: <Stamp tone="warn">Auto summary</Stamp>,
  rejected: <Stamp tone="line">Not a pivot</Stamp>,
  running: <Stamp tone="live">Analysing</Stamp>,
};

const seconds = (ms: number) => (ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`);

function tier(model: string | null): string {
  if (!model) return "rules";
  return model.includes("mini") ? "mini" : "standard";
}

function summary(t: AgentTrace): string {
  if (t.agent === "verifier" && t.verdict) {
    return t.verdict.passed ? "✓ every claim recomputed" : `✗ ${t.verdict.issues.map((i) => i.message).join(" ")}`;
  }
  if (t.agent === "explainer" && t.status === "retried") return `rewrite with feedback · “${t.output_summary}”`;
  if (t.agent === "explainer") return `draft · “${t.output_summary}”`;
  return t.output_summary;
}

function Step({ t, offset }: { t: AgentTrace; offset: number }) {
  const bad = t.status === "rejected" || t.status === "error" || t.status === "degraded";
  return (
    <details className={`trace-step${bad ? " bad" : ""}`}>
      <summary>
        <span className="at num">+{seconds(offset)}</span>
        <b>
          {AGENT[t.agent]} <span className="tier">· {tier(t.model)}</span>
        </b>
        <span className="what">{summary(t)}</span>
        <span className="ms num">{seconds(t.latency_ms)}</span>
      </summary>
      <dl>
        <dt>Status</dt><dd>{t.status}</dd>
        <dt>Model</dt><dd>{t.model ?? "deterministic"}</dd>
        <dt>Prompt</dt><dd className="num">{t.prompt_hash ?? "—"}</dd>
        <dt>Tokens</dt><dd className="num">{t.tokens.toLocaleString("en")}</dd>
        {t.verdict && (<><dt>Verdict</dt><dd><pre>{JSON.stringify(t.verdict, null, 1)}</pre></dd></>)}
      </dl>
    </details>
  );
}

function Chain({ chain, minute }: { chain: TraceChain; minute: string }) {
  let offset = 0;
  return (
    <Card title={`Pivot ${minute}`} note={<span className="num">{chain.chainId}</span>} className="trace-chain">
      <div className="trace-head">
        {OUTCOME[chain.outcome]}
        <span className="muted">
          {chain.steps.length} steps · total <span className="num">{seconds(chain.totalMs)}</span>
        </span>
        <span className="sp" />
        <Link to={`/pivot/${chain.pivotId}`}>Open pivot →</Link>
      </div>
      {chain.steps.map((t) => {
        const at = offset;
        offset += t.latency_ms;
        return <Step key={t.trace_id} t={t} offset={at} />;
      })}
    </Card>
  );
}

export default function AgentTraces() {
  const { id } = useParams();
  const { pivots } = useMatch();
  // Only chains for pivots the replay has reached, so the list grows with the match.
  const seen = new Set(pivots.map((p) => p.pivot_id));
  const chains = useTraceChains().filter((c) => seen.has(c.pivotId) && (!id || c.pivotId === id));
  const minuteOf = (pivotId: string) => {
    const p = pivots.find((x) => x.pivot_id === pivotId);
    return p ? `${p.minute}′` : pivotId;
  };

  return (
    <>
      <div className="back">
        <Link to={id ? `/pivot/${id}` : "/"}>← {id ? `Pivot ${minuteOf(id)}` : "Live board"}</Link>
      </div>
      <div className="headline">
        <Kicker>Agent trace</Kicker>
        <span className="x">Every handoff between the agents</span>
      </div>
      {chains.length === 0 && <p className="muted">No agent activity for this pivot yet.</p>}
      <div className="stack trace-list">
        {chains.map((c) => <Chain key={c.chainId} chain={c} minute={minuteOf(c.pivotId)} />)}
      </div>
    </>
  );
}
