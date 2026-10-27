// The analyst's xG race at the top of the Overview (C18, #366), Understat / Opta style: each team's
// expected goals adding up shot by shot, as a step line in its kit colour, with the goals as rings on
// the line, red cards as ticks on the axis and the AI's turning points as numbered dashed lines.
// The steps are the API's own per-shot xG (/shots); the total at the end of each line is the team
// stats' xG (the verifier's StatCalculator), which the steps add up to.
import type { MatchEvent, Pivot1 as Pivot, ShotMapShot } from "@pivot/contracts";
import { isRedCard, type Side } from "../data/view";
import { useT } from "../i18n";

const W = 780, H = 240, L = 40, R = 56, T = 20, B = 28;

export type XgStep = { t: number; total: number; goal: boolean; id: string };

/**
 * Each side's running xG, one step per shot in time order (a shot without xG adds nothing). A goal VAR
 * ruled out still counts, as it does in the team stats' xG, so the line ends on the same number.
 */
export function xgSteps(shots: readonly ShotMapShot[]): Record<Side, XgStep[]> {
  const out: Record<Side, XgStep[]> = { home: [], away: [] };
  const sum = { home: 0, away: 0 };
  for (const s of [...shots].sort((a, b) => a.t - b.t)) {
    sum[s.team] += s.xg ?? 0;
    out[s.team].push({ t: s.t, total: sum[s.team], goal: s.outcome === "goal", id: s.event_id });
  }
  return out;
}

type Props = {
  shots: readonly ShotMapShot[];
  events: readonly MatchEvent[];
  pivots: readonly Pivot[];
  /** The team stats' xG for each side, written at the end of its line. */
  totals: Record<Side, number | null>;
  names: Record<Side, string>;
  /** Seconds the line runs to: the match clock, or full time. */
  end: number;
};

export default function XgRace({ shots, events, pivots, totals, names, end }: Props) {
  const t = useT();
  const steps = xgSteps(shots);
  const last = Math.max(end, ...shots.map((s) => s.t), 90 * 60);
  const top = Math.max(1, ...Object.values(steps).map((s) => s.at(-1)?.total ?? 0), ...Object.values(totals).map((v) => v ?? 0));
  const yMax = Math.ceil(top * 2) / 2;
  const x = (s: number) => L + (s / last) * (W - L - R);
  const y = (v: number) => H - B - (v / yMax) * (H - T - B);
  const path = (side: Side) => {
    let d = `M${x(0)},${y(0)}`;
    for (const s of steps[side]) d += ` H${x(s.t)} V${y(s.total)}`;
    return `${d} H${x(Math.min(end, last))}`;
  };
  const reds = events.filter((e) => isRedCard(e));
  const turns = [...pivots].filter((p) => p.status === "confirmed" || p.status === "degraded").sort((a, b) => a.minute - b.minute);
  const ticks = [];
  for (let v = 0; v <= yMax + 1e-9; v += yMax > 2 ? 1 : 0.5) ticks.push(v);
  const minutes = [0, 15, 30, 45, 60, 75, 90].filter((m) => m * 60 <= last);
  const label = t("xg.label", {
    home: names.home, away: names.away,
    hxg: (totals.home ?? steps.home.at(-1)?.total ?? 0).toFixed(2), axg: (totals.away ?? steps.away.at(-1)?.total ?? 0).toFixed(2),
  });

  return (
    <figure className="xg-race">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} className="xg-grid" />
            <text x={L - 8} y={y(v) + 4} textAnchor="end" className="xg-axis">{v.toFixed(1)}</text>
          </g>
        ))}
        {minutes.map((m) => <text key={m} x={x(m * 60)} y={H - 8} textAnchor="middle" className="xg-axis">{m}′</text>)}
        {turns.map((p, i) => (
          <g key={p.pivot_id} className="xg-turn">
            <line x1={x(p.minute * 60)} x2={x(p.minute * 60)} y1={T} y2={H - B} />
            <circle cx={x(p.minute * 60)} cy={T} r={9} />
            <text x={x(p.minute * 60)} y={T + 4} textAnchor="middle">{i + 1}</text>
          </g>
        ))}
        {reds.map((e) => <rect key={e.event_id} className="xg-red" x={x(e.t) - 3} y={H - B - 10} width={6} height={10} rx={1}><title>{t("xg.red", { minute: e.clock_label.replace(/'/g, "′") })}</title></rect>)}
        {(["home", "away"] as const).map((side) => (
          <g key={side} style={{ color: `var(--pv-${side})` }}>
            <path d={path(side)} className="xg-line" />
            {steps[side].filter((s) => s.goal).map((s) => (
              <circle key={s.id} cx={x(s.t)} cy={y(s.total)} r={6} className="xg-goal" />
            ))}
            <text x={x(Math.min(end, last)) + 6} y={y(totals[side] ?? steps[side].at(-1)?.total ?? 0) + 4} className="xg-end">
              {(totals[side] ?? steps[side].at(-1)?.total ?? 0).toFixed(2)}
            </text>
          </g>
        ))}
      </svg>
      <figcaption className="xg-key">
        <span className="home">{names.home}</span>
        <span className="away">{names.away}</span>
        <span className="k-goal">{t("xg.keyGoal")}</span>
        {reds.length > 0 && <span className="k-red">{t("xg.keyRed")}</span>}
        {turns.length > 0 && <span className="k-turn">{t("xg.keyTurn")}</span>}
      </figcaption>
    </figure>
  );
}
