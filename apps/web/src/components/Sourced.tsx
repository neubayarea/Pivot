import type { ReactNode } from "react";
import type { Claim, StatRef } from "@pivot/contracts";
import { useMatch } from "../data/match";
import { isMessageKey, useT, type T } from "../i18n";

const metricLabel = (m: StatRef["metric"], t: T) => {
  const key = `metric.${m}`;
  return isMessageKey(key) ? t(key) : m[0].toUpperCase() + m.slice(1).replaceAll("_", " ");
};

export function formatValue(c: Claim): string {
  if (c.unit === "pct") return `${c.value}%`;
  if (c.unit === "index") return `${c.value > 0 ? "+" : c.value < 0 ? "−" : ""}${Math.abs(c.value).toFixed(2)}`;
  return String(c.value);
}

/** A number with its source: hover or focus shows the stat_ref it was read from. */
export default function Sourced({ claim, className = "", children }: { claim: Claim; className?: string; children: ReactNode }) {
  const { teams, playerName } = useMatch();
  const t = useT();
  const { metric, team, player_id, window } = claim.stat_ref;
  return (
    <span className={`src ${className}`.trim()} tabIndex={0}>
      {children}
      <span className="tip" role="tooltip">
        <b>{metricLabel(metric, t)}</b>
        <span>{teams[team].name}{player_id ? ` · ${playerName(player_id)}` : ""}</span>
        <span>
          {window[0]}′–{window[1]}′ · {formatValue(claim)}
        </span>
        <code>stat_ref.{metric}</code>
      </span>
    </span>
  );
}
