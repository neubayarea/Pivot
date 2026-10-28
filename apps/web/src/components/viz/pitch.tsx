// The pitch the match pictures (Bx12) draw on: 105 x 68 m at 5 px a metre, the same markings and
// tokens as Pitch.tsx. The API sends every point in the acting team's attacking view (CONV-002):
// own goal at x = 0, the opponent's at x = 105. One team is drawn as sent (attacking to the right);
// for two teams on one pitch the away side is flipped back with `flip`.
import type { ReactNode } from "react";
import type { Side, SquadPlayer } from "../../data/view";
import { useT } from "../../i18n";
import Grass from "../Grass";

export const S = 5;
export const W = 105 * S;
export const H = 68 * S;
const LINE = { fill: "none", stroke: "var(--pv-pitch-line)", strokeWidth: 2 };

/** A team-view point in pixels; `flip` turns the away side round so it attacks to the left. */
export function toPx(x: number, y: number, flip = false): [number, number] {
  return flip ? [(105 - x) * S, (68 - y) * S] : [x * S, y * S];
}

export const teamColor = (side: Side) => (side === "home" ? "var(--pv-home)" : "var(--pv-away)");

export type Who = { name: string; shirt: string };
/** Names and shirt numbers by player id, from the squads the page already has (MatchView.squads). */
export function whoFrom(squads?: Record<Side, SquadPlayer[]>): (id: string | null | undefined) => Who {
  const map = new Map<string, Who>();
  for (const side of ["home", "away"] as const) {
    for (const p of squads?.[side] ?? []) map.set(p.player_id, { name: p.name, shirt: p.shirt === null ? "" : String(p.shirt) });
  }
  return (id) => (id ? (map.get(id) ?? { name: id, shirt: "" }) : { name: "", shirt: "" });
}

/** "38'" from the API, written with the prime the rest of the site uses. */
export const minuteText = (clock: string) => clock.replace(/'/g, "′");

function Markings() {
  return (
    <>
      <rect x={1} y={1} width={W - 2} height={H - 2} {...LINE} />
      <line x1={W / 2} x2={W / 2} y1={0} y2={H} {...LINE} />
      <circle cx={W / 2} cy={H / 2} r={9.15 * S} {...LINE} />
      <circle cx={W / 2} cy={H / 2} r={3} fill="var(--pv-pitch-line)" />
      {[0, W - 16.5 * S].map((x) => (
        <rect key={x} x={x} y={((68 - 40.3) / 2) * S} width={16.5 * S} height={40.3 * S} {...LINE} />
      ))}
      {[0, W - 5.5 * S].map((x) => (
        <rect key={x} x={x} y={((68 - 18.3) / 2) * S} width={5.5 * S} height={18.3 * S} {...LINE} />
      ))}
    </>
  );
}

/** The pitch with `children` drawn over the markings. `under` goes below the lines (heatmap cells). */
export function VizPitch({ label, children, under, arrow }: {
  label: string; children?: ReactNode; under?: ReactNode;
  /** Show "attacks this way" under the pitch: one team, drawn attacking to the right. */
  arrow?: boolean;
}) {
  const t = useT();
  return (
    <div className="viz-pitch">
      <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label={label}>
        <Grass w={W} h={H} />
        {under}
        <g className="viz-lines"><Markings /></g>
        {children}
      </svg>
      {arrow && <p className="viz-arrow">{t("viz.attacks")}</p>}
    </div>
  );
}
