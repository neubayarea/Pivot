// Game state (C19, #385): how each side played while level, ahead and behind, from the API's
// StatCalculator windows cut at the goals. One row per state, each number with a small bar.
import type { CSSProperties } from "react";
import type { GameState, Side, StateLine } from "../../data/analysis";
import { useT, type MessageKey } from "../../i18n";

const COLS = [["xg_per90", "xg_per90"], ["xga_per90", "xga_per90"], ["possession_pct", "possession_pct"], ["field_tilt_pct", "field_tilt"]] as const;
type Col = (typeof COLS)[number][0];
const fmt = (c: Col, v: number) => (c.endsWith("per90") ? v.toFixed(2) : `${Math.round(v)}%`);

/** The row and side where a team made the most xG per 90: "most dangerous when behind". */
export function mostDangerous(rows: readonly GameState[]): { row: GameState; side: Side } | null {
  let best: { row: GameState; side: Side } | null = null;
  for (const row of rows) {
    if (row.minutes < 5) continue;
    for (const side of ["home", "away"] as const) {
      if (!best || row[side].xg_per90 > best.row[best.side].xg_per90) best = { row, side };
    }
  }
  return best;
}

/** A state's name, as the side in question lived it: "level", "ahead", "behind". */
export const stateFor = (s: GameState["state"], side: Side): "level" | "ahead" | "behind" =>
  s === "level" ? "level" : (s === "home_leading") === (side === "home") ? "ahead" : "behind";

export default function GameStateTable({ rows, names }: { rows: GameState[]; names: Record<Side, string> }) {
  const t = useT();
  const max = (c: Col) => Math.max(...rows.flatMap((r) => [r.home[c], r.away[c]]), c.endsWith("per90") ? 1 : 100);
  const cell = (r: GameState, side: Side, c: Col) => {
    const v = (r[side] as StateLine)[c];
    return (
      <td key={`${side}-${c}`} className="num" style={{ "--tc": `var(--pv-${side})`, "--w": `${(v / max(c)) * 100}%` } as CSSProperties}>
        <span className="rp-cell">{fmt(c, v)}</span>
        <span className="rp-inline" aria-hidden="true"><i /></span>
      </td>
    );
  };
  const stateName = (s: GameState["state"]) => s === "level" ? t("rp.gs.level") : t("rp.gs.ahead", { team: names[s === "home_leading" ? "home" : "away"] });
  return (
    <div className="rp-scroll">
      <table className="rp-gs">
        <caption className="sr-only">{t("rp.gs.caption")}</caption>
        <thead>
          <tr>
            <th scope="col" rowSpan={2}>{t("rp.gs.state")}</th>
            <th scope="col" rowSpan={2} className="num">{t("rp.gs.minutes")}</th>
            <th scope="colgroup" colSpan={4} className="home">{names.home}</th>
            <th scope="colgroup" colSpan={4} className="away">{names.away}</th>
          </tr>
          <tr>
            {(["home", "away"] as const).flatMap((side) => COLS.map(([c, k]) => (
              <th key={`${side}-${c}`} scope="col" title={t(`metric.${k}.def` as MessageKey)}>{t(`metric.${k}.short` as MessageKey)}</th>
            )))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.state}>
              <th scope="row">{stateName(r.state)}</th>
              <td className="num">{Math.round(r.minutes)}′</td>
              {(["home", "away"] as const).flatMap((side) => COLS.map(([c]) => cell(r, side, c)))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
