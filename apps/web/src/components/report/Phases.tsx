// Match phases (C19, #385), The Analyst style: the match in 15-minute blocks, home's bar up and away's
// down from one baseline, for one metric at a time. Goals sit on their block as rings beside the bar;
// the AI's turning points as numbered yellow badges over the block they fall in.
import { useState } from "react";
import type { Phase, Side } from "../../data/analysis";
import { blockOf, reached } from "../../data/analysis";
import { usePrefs, type MessageKey } from "../../i18n";
import Segmented from "../Segmented";

export const PHASE_METRICS = ["xg", "field_tilt_pct", "possession_pct", "ppda"] as const;
export type PhaseMetric = (typeof PHASE_METRICS)[number];
/** The metric.* key that names and defines each one. */
export const METRIC_KEY: Record<PhaseMetric, string> = { xg: "xg", field_tilt_pct: "field_tilt", possession_pct: "possession_pct", ppda: "ppda" };

const fmt = (m: PhaseMetric, v: number | null) => (v === null ? "–" : m === "xg" ? v.toFixed(2) : m === "ppda" ? v.toFixed(1) : `${Math.round(v)}%`);

/** The block where one side was furthest ahead on `m` (for PPDA, the lower press number is ahead). */
export function bestSpell(phases: readonly Phase[], m: PhaseMetric): { i: number; side: Side } | null {
  let best: { i: number; side: Side; gap: number } | null = null;
  for (let i = 0; i < phases.length; i++) {
    const h = phases[i].home[m], a = phases[i].away[m];
    if (h === null || a === null) continue;
    const gap = m === "ppda" ? a - h : h - a;
    if (gap !== 0 && (!best || Math.abs(gap) > Math.abs(best.gap))) best = { i, side: gap > 0 ? "home" : "away", gap };
  }
  return best && { i: best.i, side: best.side };
}

type Mark = { label: string; side: Side; kind: "goal" | "pivot"; n?: number; text: string };

const W = 1100, H = 250, L = 52, R = 12, MID = 122, AMP = 92;

export default function Phases({ phases, names, marks, onMetric }: { phases: Phase[]; names: Record<Side, string>; marks: Mark[]; onMetric?: (m: PhaseMetric) => void }) {
  const { t } = usePrefs();
  const [m, setM] = useState<PhaseMetric>("xg");
  const pick = (v: PhaseMetric) => { setM(v); onMetric?.(v); };
  const top = Math.max(...phases.flatMap((p) => [p.home[m] ?? 0, p.away[m] ?? 0]), m === "xg" ? 0.5 : 1);
  const cw = (W - L - R) / phases.length;
  const bw = Math.min(56, cw * 0.5);
  const h = (v: number | null) => ((v ?? 0) / top) * AMP;
  const span = (p: Phase, i: number) => `${p.from}′–${p.to}′${i === phases.length - 1 || p.to === 45 ? "+" : ""}`;
  return (
    <div className="rp-phases">
      <Segmented label={t("rp.ph.metric")} value={m} onChange={pick}
        options={PHASE_METRICS.map((k) => ({ value: k, label: t(`metric.${METRIC_KEY[k]}.short` as MessageKey) }))} />
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("rp.ph.label", { metric: t(`metric.${METRIC_KEY[m]}.short` as MessageKey) })}>
        <line x1={L} x2={W - R} y1={MID} y2={MID} className="rp-base" />
        <text x={L - 8} y={MID - AMP + 4} textAnchor="end" className="rp-axis">{names.home}</text>
        <text x={L - 8} y={MID + AMP} textAnchor="end" className="rp-axis">{names.away}</text>
        {phases.map((p, i) => {
          const cx = L + cw * (i + 0.5);
          const hh = h(p.home[m]), ah = h(p.away[m]);
          // A block the match has not reached yet: a grey outline, "not started", no bars.
          if (!reached(p)) {
            return (
              <g key={p.from} className="rp-todo">
                <rect x={cx - bw / 2} y={MID - AMP / 2} width={bw} height={AMP} rx={4} />
                <text x={cx} y={MID + 4} textAnchor="middle">{t("rp.ph.notStarted")}</text>
                <text x={cx} y={H - 4} textAnchor="middle" className="rp-axis">{span(p, i)}</text>
              </g>
            );
          }
          const goals = marks.filter((k) => k.kind === "goal" && blockOf(phases, k.label) === i);
          const pivots = marks.filter((k) => k.kind === "pivot" && blockOf(phases, k.label) === i);
          return (
            <g key={p.from}>
              <rect x={cx - bw / 2} y={MID - hh - 1} width={bw} height={Math.max(hh, 0.5)} rx={4} className="rp-bar home">
                <title>{`${span(p, i)} ${names.home}: ${fmt(m, p.home[m])}`}</title>
              </rect>
              <rect x={cx - bw / 2} y={MID + 1} width={bw} height={Math.max(ah, 0.5)} rx={4} className="rp-bar away">
                <title>{`${span(p, i)} ${names.away}: ${fmt(m, p.away[m])}`}</title>
              </rect>
              <text x={cx} y={MID - hh - 6} textAnchor="middle" className="rp-val">{fmt(m, p.home[m])}</text>
              <text x={cx} y={MID + ah + 14} textAnchor="middle" className="rp-val">{fmt(m, p.away[m])}</text>
              <text x={cx} y={H - 4} textAnchor="middle" className="rp-axis">{span(p, i)}</text>
              {goals.map((g, k) => (
                <circle key={k} cx={cx + bw / 2 + 9} cy={g.side === "home" ? MID - 10 - k * 14 : MID + 10 + k * 14} r={5} className={`rp-goal ${g.side}`}>
                  <title>{g.text}</title>
                </circle>
              ))}
              {pivots.map((v, k) => (
                <g key={`p${k}`} className="rp-pivot">
                  <circle cx={cx - bw / 2 - 12 - k * 20} cy={MID - AMP + 4} r={9} />
                  <text x={cx - bw / 2 - 12 - k * 20} y={MID - AMP + 8} textAnchor="middle">{v.n}</text>
                  <title>{v.text}</title>
                </g>
              ))}
            </g>
          );
        })}
      </svg>
      <p className="rp-key">
        <span className="home">{names.home}</span>
        <span className="away">{names.away}</span>
        <span className="k-goal">{t("xg.keyGoal")}</span>
        <span className="k-turn">{t("xg.keyTurn")}</span>
        <span className="muted" title={t(`metric.${METRIC_KEY[m]}.def` as MessageKey)}>{t(`metric.${METRIC_KEY[m]}.def` as MessageKey)}</span>
      </p>
    </div>
  );
}
