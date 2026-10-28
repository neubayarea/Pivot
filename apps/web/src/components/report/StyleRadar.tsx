// Style profile (C19, #385), StatsBomb-style radar: eight team numbers as percentiles against the
// site's finished matches (the API's baseline), both teams on one radar. For PPDA the API already
// turns the percentile round, so further out always means more of that style (a harder press).
import type { CSSProperties } from "react";
import type { MatchAnalysis, Side } from "../../data/analysis";
import { useT, type MessageKey } from "../../i18n";
import { count, or0 } from "./fmt";

const S = 340, C = S / 2, RAD = 120;

/** The point for value `v` (0–100) on axis `i` of `n`, the first axis straight up. */
export function radarPoint(i: number, n: number, v: number): [number, number] {
  const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
  const r = (Math.max(0, Math.min(100, v)) / 100) * RAD;
  return [C + r * Math.cos(a), C + r * Math.sin(a)];
}

export default function StyleRadar({ profile, names }: { profile: MatchAnalysis["profile"]; names: Record<Side, string> }) {
  const t = useT();
  const n = profile.metrics.length;
  const label = (id: string) => t(`rp.pf.${id}` as MessageKey);
  const poly = (vals: readonly (number | null)[]) => vals.map((v, i) => radarPoint(i, n, or0(v)).join(",")).join(" ");
  return (
    <div className="rp-radar">
      <svg viewBox={`-70 -10 ${S + 140} ${S + 20}`} role="img" aria-label={t("rp.pf.label", { n: profile.baseline_matches })}>
        {[25, 50, 75, 100].map((r) => <polygon key={r} points={poly(Array(n).fill(r))} className="rp-ring" />)}
        {profile.metrics.map((id, i) => {
          const [x, y] = radarPoint(i, n, 100);
          const [lx, ly] = radarPoint(i, n, 118);
          return (
            <g key={id}>
              <line x1={C} y1={C} x2={x} y2={y} className="rp-spoke" />
              <text x={lx} y={ly + 4} textAnchor={Math.abs(lx - C) < 8 ? "middle" : lx > C ? "start" : "end"} className="rp-axis rp-radar-k">{label(id)}</text>
            </g>
          );
        })}
        <text x={C + 3} y={C - RAD / 2 - 2} className="rp-axis rp-ring-k">50</text>
        {(["away", "home"] as const).map((side) => (
          <g key={side} style={{ color: `var(--pv-${side})` }}>
            <polygon points={poly(profile[side])} className="rp-area" />
            {profile[side].map((v, i) => {
              const [x, y] = radarPoint(i, n, or0(v));
              return <circle key={i} cx={x} cy={y} r={4} className="rp-vertex"><title>{`${names[side]} · ${label(profile.metrics[i])}: ${count(v)}`}</title></circle>;
            })}
          </g>
        ))}
      </svg>
      <table className="rp-pf-table">
        <caption className="sr-only">{t("rp.pf.label", { n: profile.baseline_matches })}</caption>
        <thead><tr><th scope="col">{t("rp.pf.metric")}</th><th scope="col" className="home">{names.home}</th><th scope="col" className="away">{names.away}</th></tr></thead>
        <tbody>
          {profile.metrics.map((id, i) => (
            <tr key={id}>
              <th scope="row">{label(id)}</th>
              {(["home", "away"] as const).map((s) => (
                <td key={s} className="num" style={{ "--tc": `var(--pv-${s})`, "--w": `${or0(profile[s][i])}%` } as CSSProperties}>
                  {count(profile[s][i])}<span className="rp-inline" aria-hidden="true"><i /></span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
