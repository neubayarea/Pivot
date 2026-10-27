// The analyst's key numbers at the top of the Overview (C18, #366): xG, shots on target, field tilt,
// PPDA and possession for both teams, straight from the team stats (/stats, the verifier's
// StatCalculator). Each one says what it is on hover, from the shared metric.* definitions.
import type { CSSProperties } from "react";
import type { TeamStatsReport } from "@pivot/contracts";
import type { Side } from "../data/view";
import { useT, type MessageKey } from "../i18n";
import { statText } from "./TeamStats";

/** The team-stats metric for each card, and the metric.* key that names and defines it. */
export const KEY_METRICS = [
  ["xg", "xg"], ["shots_on_target", "shots_on_target"], ["field_tilt_pct", "field_tilt"], ["ppda", "ppda"], ["possession_pct", "possession_pct"],
] as const;

export default function KeyMetrics({ report, names }: { report: TeamStatsReport | null; names: Record<Side, string> }) {
  const t = useT();
  const scope = report?.scopes.find((s) => s.scope === "match") ?? report?.scopes[0];
  if (!report || !scope) return null;
  return (
    <dl className="key-metrics">
      {KEY_METRICS.map(([id, key]) => {
        const info = report.metrics.find((m) => m.metric === id);
        if (!info) return null;
        const h = scope.home[id] ?? null, a = scope.away[id] ?? null;
        // PPDA is a ratio the card shows to one decimal (5.3), not rounded to a whole number.
        const show = (v: number | null) => (v !== null && info.unit === "ratio" ? v.toFixed(1) : statText(v, info));
        // Who leads: the higher number, except PPDA where lower is the harder press.
        const lead: Side | null = h === null || a === null || h === a ? null : (id === "ppda" ? h < a : h > a) ? "home" : "away";
        const def = t(`metric.${key}.def` as MessageKey);
        return (
          <div key={id} className="kmet" title={def}>
            <dt>{t(`metric.${key}.short` as MessageKey)}<span className="sr-only">: {def}</span></dt>
            <dd>
              <span className={`num h${lead === "home" ? " win" : ""}`} style={{ "--tc": "var(--pv-home)" } as CSSProperties} aria-label={`${names.home} ${show(h)}`}>{show(h)}</span>
              <span className={`num a${lead === "away" ? " win" : ""}`} style={{ "--tc": "var(--pv-away)" } as CSSProperties} aria-label={`${names.away} ${show(a)}`}>{show(a)}</span>
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
