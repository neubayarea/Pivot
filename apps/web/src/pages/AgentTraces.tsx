import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import type { AgentTrace, Pivot1 as Pivot } from "@pivot/contracts";
import Button from "../components/Button";
import Card from "../components/Card";
import Kicker from "../components/Kicker";
import { pivotHeadline } from "../components/PivotList";
import Stamp from "../components/Stamp";
import { useClock } from "../data/clock";
import { useFixture, useMatch } from "../data/match";
import {
  fixtureTraceSource, liveTraceSource, refMinute, useTraceChains, type TraceChain, type TraceState,
} from "../data/traces";
import { isMessageKey, useT, type T } from "../i18n";
import "../styles/traces.css";

// S4 · Agent trace (US-08). One card per detect chain, one row per agent handoff: the Judge's
// call, each Explainer draft, what the Verifier sent back and why, and whether the template had
// to write the final text. Rows open for status, model, prompt hash, tokens and the verdict.

const OUTCOME_TONE = { confirmed: "ok", degraded: "warn", rejected: "line", running: "live" } as const;

/** Long feedback (a schema error lists every metric) is cut in the row; the verdict below has it whole. */
const clip = (text: string, max = 140) => (text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text);

const seconds = (ms: number) => (ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`);

/** A key that exists for some codes only (agents, statuses, issue codes); the raw value otherwise. */
function label(t: T, prefix: string, value: string): string {
  const key = `${prefix}.${value}`;
  return isMessageKey(key) ? t(key) : value;
}

/** "is_pivot=true severity=3: reason" is how the worker writes the Judge's call. */
function judgeCall(summary: string): { pivot: boolean; severity: number | null; reason: string } | null {
  const m = /^is_pivot=(true|false)(?: severity=(\d))?:?\s*(.*)$/s.exec(summary);
  return m ? { pivot: m[1] === "true", severity: m[2] ? Number(m[2]) : null, reason: m[3] } : null;
}

function summary(t: T, s: AgentTrace, draft: number): ReactNode {
  if (s.agent === "judge") {
    const call = judgeCall(s.output_summary);
    if (!call) return s.output_summary;
    return (
      <>
        <b>{call.pivot ? t("trace.judge.yes", { n: call.severity ?? "?" }) : t("trace.judge.no")}</b>
        {call.reason && <> · {call.reason}</>}
      </>
    );
  }
  if (s.agent === "verifier" && s.verdict) {
    if (s.verdict.passed) return <b>{t("trace.verifier.pass")}</b>;
    return (
      <>
        <b>{t("trace.verifier.fail")}</b>
        {s.verdict.issues.map((i, n) => (
          <span key={n} className="issue">
            {t("trace.reason", { code: label(t, "trace.issue", i.code), message: clip(i.message) })}
          </span>
        ))}
      </>
    );
  }
  if (s.agent === "explainer") {
    return (
      <>
        <b>{draft === 0 ? t("trace.explainer.draft") : t("trace.explainer.rewrite", { n: draft })}</b> · “{clip(s.output_summary)}”
      </>
    );
  }
  if (s.agent === "template") return <><b>{t("trace.template.wrote")}</b> · “{s.output_summary}”</>;
  return s.output_summary;
}

function Step({ s, offset, draft }: { s: AgentTrace; offset: number; draft: number }) {
  const t = useT();
  const bad = s.status === "rejected" || s.status === "error" || s.status === "degraded";
  return (
    <details className={`trace-step${bad ? " bad" : ""}`}>
      <summary>
        <span className="at num">+{seconds(offset)}</span>
        <span className="who">
          {label(t, "trace.agent", s.agent)} <span className="tier">· {s.model ?? t("trace.rules")}</span>
        </span>
        <span className="what">{summary(t, s, draft)}</span>
        <span className="ms num">{seconds(s.latency_ms)}</span>
      </summary>
      <dl>
        <dt>{t("trace.field.status")}</dt><dd>{label(t, "trace.status", s.status)}</dd>
        <dt>{t("trace.field.model")}</dt><dd>{s.model ?? t("trace.rules")}</dd>
        <dt>{t("trace.field.prompt")}</dt><dd className="num">{s.prompt_hash ?? "—"}</dd>
        <dt>{t("trace.field.tokens")}</dt><dd className="num">{s.tokens.toLocaleString("en")}</dd>
        {s.verdict && (<><dt>{t("trace.field.verdict")}</dt><dd><pre>{JSON.stringify(s.verdict, null, 1)}</pre></dd></>)}
      </dl>
    </details>
  );
}

function Chain({ chain, pivot }: { chain: TraceChain; pivot: Pivot | undefined }) {
  const t = useT();
  const { teams } = useMatch();
  const { minute } = useClock();
  const at = pivot?.minute ?? refMinute(chain.pivotId);
  const when = at === null ? "" : `${minute(at)}′ · `;
  const title = pivot ? `${when}${pivotHeadline(pivot, teams, t)}` : `${when}${t("trace.candidate")}`;
  let offset = 0;
  let drafts = 0;
  return (
    <Card title={title} note={<span className="num">{chain.chainId}</span>} className="trace-chain">
      <div className="trace-head">
        <Stamp tone={OUTCOME_TONE[chain.outcome]}>{t(`trace.outcome.${chain.outcome}`)}</Stamp>
        <span className="facts muted">
          <span>{t("trace.steps", { n: chain.steps.length, time: seconds(chain.totalMs) })}</span>
          {chain.outcome !== "rejected" && (
            <>
              <span>{t("trace.rewrites", { n: chain.rewrites })}</span>
              <span>{t(chain.template ? "trace.final.template" : "trace.final.ai")}</span>
            </>
          )}
        </span>
        <span className="sp" />
        {pivot && <Link to={`/pivot/${chain.pivotId}`}>{t("trace.openPivot")}</Link>}
      </div>
      {chain.rejections.length > 0 && (
        <div className="trace-why">
          <b>{t("trace.why", { n: chain.rejections.length })}</b>
          <ol>
            {chain.rejections.map((i, n) => <li key={n}>{t("trace.reason", { code: label(t, "trace.issue", i.code), message: clip(i.message) })}</li>)}
          </ol>
        </div>
      )}
      {chain.steps.map((s) => {
        const start = offset;
        offset += s.latency_ms;
        const draft = s.agent === "explainer" ? drafts++ : 0;
        return <Step key={s.trace_id} s={s} offset={start} draft={draft} />;
      })}
    </Card>
  );
}

export default function AgentTraces() {
  const { id } = useParams();
  const fixture = useFixture();
  const { match, pivots } = useMatch();
  const [reload, setReload] = useState(0);
  // A new or settled pivot means new steps: fetch again.
  const version = pivots.map((p) => `${p.pivot_id}=${p.status}`).join();
  const source = fixture ? fixtureTraceSource : liveTraceSource;
  const state = useTraceChains(source, match.match_id, id, version, reload);
  return <TraceList state={state} pivotId={id} onRetry={() => setReload((n) => n + 1)} />;
}

/** The page for one state of the fetch; `pivotId` when it is one pivot's trace (`/trace/:id`). */
export function TraceList({ state, pivotId: id, onRetry }: { state: TraceState; pivotId?: string; onRetry: () => void }) {
  const t = useT();
  const { match, pivots } = useMatch();
  const { minute } = useClock();
  const pivotOf = (pivotId: string) => pivots.find((p) => p.pivot_id === pivotId);
  // Only what the match has reached, so a replay from kick-off does not give away later pivots.
  const reached = (c: TraceChain) => {
    const at = refMinute(c.pivotId);
    return !!pivotOf(c.pivotId) || (at !== null && at * 60 <= match.clock);
  };
  const chains = state.kind === "ready" ? state.chains.filter((c) => !!id || reached(c)) : [];
  const own = id ? pivotOf(id) : undefined;

  return (
    <>
      <div className="back">
        {id && own ? (
          <Link to={`/pivot/${id}`}>{t("trace.backPivot", { minute: minute(own.minute) })}</Link>
        ) : (
          <Link to="/">{t("detail.back")}</Link>
        )}
      </div>
      <div className="headline">
        <Kicker>{t("trace.kicker")}</Kicker>
        <span className="x">{t("trace.title")}</span>
        <span className="sp" />
        {id && <Link to="/trace">{t("trace.all")}</Link>}
      </div>
      <p className="trace-intro muted">{t("trace.intro")}</p>
      <div className="stack trace-list">
        {state.kind === "loading" && (
          <div aria-busy="true" className="sk-lines">
            <p className="sr-only" role="status">{t("trace.loading")}</p>
            {[0, 1, 2, 3, 4].map((i) => <span key={i} className="sk sk-line" aria-hidden="true" />)}
          </div>
        )}
        {state.kind === "error" && (
          <div role="alert" className="run-failed">
            <p>{t("trace.error")}</p>
            <Button onClick={onRetry}>{t("common.retryNow")}</Button>
          </div>
        )}
        {state.kind === "ready" && chains.length === 0 && (
          <p className="trace-empty muted" role="status">{t(id ? "trace.empty.pivot" : "trace.empty.match")}</p>
        )}
        {chains.map((c) => <Chain key={c.chainId} chain={c} pivot={pivotOf(c.pivotId)} />)}
      </div>
    </>
  );
}
