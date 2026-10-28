// Game state (C19, #385): how each side played while level, ahead and behind, from the API's
// StatCalculator windows cut at the goals. One row per state, each number with a small bar.
import type { CSSProperties } from "react";
import { isNum, type GameState, type Side, type StateLine } from "../../data/analysis";
import { useT, type MessageKey } from "../../i18n";
import { count, num, or0, pct } from "./fmt";

const COLS = [["xg_per90", "xg_per90"], ["xga_per90", "xga_per90"], ["possession_pct", "possession_pct"], ["field_tilt_pct", "field_tilt"]] as const;
type Col = (typeof COLS)[number][0];
const fmt = (c: Col, v: number | null) => (c.endsWith("per90") ? num(v) : pct(v));
const per90 = (c: Col) => c.endsWith("per90");

/**
 * C21 (P0): a score state this short says little per 90 minutes (four minutes level with one chance
 * reads 20 xG/90), so, as Opta and StatsBomb do, its xG is shown as it stands, not scaled up, and the
 * takeaway sentence leaves it out.
 */
export const SHORT_STATE = 15;
export const isShort = (r: GameState) => !isNum(r.minutes) || r.minutes < SHORT_STATE;
/** The xG of a short state as it stands: the API's rate brought back to the minutes played. */
const asPlayed = (perNinety: number | null, minutes: number | null) => (isNum(perNinety) && isNum(minutes) ? (perNinety * minutes) / 90 : null);

/** The row and side where a team made the most xG per 90: "most dangerous when behind". */
export function mostDangerous(rows: readonly GameState[]): { row: GameState; side: Side } | null {
  let best: { row: GameState; side: Side } | null = null;
  for (const row of rows) {
    if (isShort(row)) continue;
    for (const side of ["home", "away"] as const) {
      const v = row[side].xg_per90;
      if (isNum(v) && (!best || v > or0(best.row[best.side].xg_per90))) best = { row, side };
    }
  }
  return best;
}

/** A state's name, as the side in question lived it: "level", "ahead", "behind". */
export const stateFor = (s: GameState["state"], side: Side): "level" | "ahead" | "behind" =>
  s === "level" ? "level" : (s === "home_leading") === (side === "home") ? "ahead" : "behind";

export default function GameStateTable({ rows, names }: { rows: GameState[]; names: Record<Side, string> }) {
  const t = useT();
  const max = (c: Col) => Math.max(...rows.filter((r) => !per90(c) || !isShort(r)).flatMap((r) => [or0(r.home[c]), or0(r.away[c])]), per90(c) ? 1 : 100);
  const cell = (r: GameState, side: Side, c: Col) => {
    const v = (r[side] as StateLine)[c];
    if (per90(c) && isShort(r)) {
      const raw = asPlayed(v, r.minutes);
      return (
        <td key={`${side}-${c}`} className="num rp-short" title={t("rp.gs.shortNote")}>
          <span className="rp-cell">{num(raw)}</span>
          <small className="rp-cell-k">{t(c === "xg_per90" ? "rp.gs.xgRaw" : "rp.gs.xgaRaw")}</small>
        </td>
      );
    }
    return (
      <td key={`${side}-${c}`} className="num" style={{ "--tc": `var(--pv-${side})`, "--w": `${(or0(v) / max(c)) * 100}%` } as CSSProperties}>
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
              <th scope="row">{stateName(r.state)}{isShort(r) && <small className="rp-short-note">{t("rp.gs.shortNote")}</small>}</th>
              <td className="num">{isNum(r.minutes) ? `${count(r.minutes)}′` : "–"}</td>
              {(["home", "away"] as const).flatMap((side) => COLS.map(([c]) => cell(r, side, c)))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
