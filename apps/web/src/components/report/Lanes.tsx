// Attacking lanes (C19, #385), Opta's "attacking sides": for each team, how often it got into the
// final third down its left, through the middle and down its right, and the xG each lane made, as
// three arrows on a pitch (attacking to the right), their width the lane's share of the entries.
import type { Lanes as LanesData, Side } from "../../data/analysis";
import { useT } from "../../i18n";
import { count, num, or0 } from "./fmt";

export const LANES = ["left", "centre", "right"] as const;
const W = 420, H = 272;

/** Each lane's share of the entries, in whole per cent. */
export function laneShares(l: LanesData): Record<(typeof LANES)[number], number> {
  const total = LANES.reduce((n, k) => n + or0(l[k]?.entries), 0) || 1;
  const of = (k: (typeof LANES)[number]) => Math.round((or0(l[k]?.entries) / total) * 100);
  return { left: of("left"), centre: of("centre"), right: of("right") };
}

function Pitch({ side, lanes, name }: { side: Side; lanes: LanesData; name: string }) {
  const t = useT();
  const share = laneShares(lanes);
  // Attacking to the right, the team's left is the top third of the drawing.
  const band = { left: H / 6, centre: H / 2, right: (5 * H) / 6 };
  return (
    <figure className="rp-lane" style={{ color: `var(--pv-${side})` }}>
      <figcaption className="rp-row">{name}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={LANES.map((k) => `${t(`rp.ln.${k}`)} ${share[k]}%, xG ${num(lanes[k]?.xg)}`).join("; ")}>
        <rect x={1} y={1} width={W - 2} height={H - 2} rx={6} className="rp-turf" />
        <line x1={W / 2} x2={W / 2} y1={1} y2={H - 1} className="rp-turf-line" />
        <line x1={(W * 2) / 3} x2={(W * 2) / 3} y1={1} y2={H - 1} className="rp-turf-line third" />
        <line x1={1} x2={W - 1} y1={H / 3} y2={H / 3} className="rp-turf-line lane" />
        <line x1={1} x2={W - 1} y1={(2 * H) / 3} y2={(2 * H) / 3} className="rp-turf-line lane" />
        {LANES.map((k) => {
          const y = band[k];
          const th = 6 + (share[k] / 100) * 34;
          return (
            <g key={k}>
              <path d={`M${W * 0.18},${y - th / 2} H${W * 0.74} V${y - th / 2 - 8} L${W * 0.86},${y} L${W * 0.74},${y + th / 2 + 8} V${y + th / 2} H${W * 0.18} Z`} className="rp-arrow">
                <title>{`${t(`rp.ln.${k}`)}: ${t("rp.ln.entries", { n: count(lanes[k]?.entries) })}, xG ${num(lanes[k]?.xg)}`}</title>
              </path>
              <text x={W * 0.2} y={y - th / 2 - 6} className="rp-lane-k">{t(`rp.ln.${k}`)}</text>
              <text x={W * 0.88} y={y - 2} className="rp-lane-pct">{share[k]}%</text>
              <text x={W * 0.88} y={y + 14} className="rp-lane-xg">{`${t("metric.xg.short")} ${num(lanes[k]?.xg)}`}</text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

export default function Lanes({ lanes, names }: { lanes: Record<Side, LanesData>; names: Record<Side, string> }) {
  return (
    <div className="rp-lanes">
      <Pitch side="home" lanes={lanes.home} name={names.home} />
      <Pitch side="away" lanes={lanes.away} name={names.away} />
    </div>
  );
}
