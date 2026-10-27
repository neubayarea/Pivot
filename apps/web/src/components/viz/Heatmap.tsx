// Heatmap (Bx12): where one team, or one player, spent their time, drawn attacking to the right.
// Each cell's shade is its share of the busiest cell. The API counts tracking-frame seconds, or
// on-ball actions when a match has no frames; the analyst legend says which.
import type { HeatmapReport } from "@pivot/contracts";
import type { Side, SquadPlayer } from "../../data/view";
import { usePrefs } from "../../i18n";
import { H, VizPitch, W, teamColor, whoFrom } from "./pitch";
import "../../styles/viz.css";

export type HeatmapProps = {
  data: HeatmapReport;
  side: Side;
  /** One player of that side instead of the whole team. */
  playerId?: string | null;
  squads?: Record<Side, SquadPlayer[]>;
  teamNames?: Record<Side, string>;
};

/** A curve, so the middling cells are not all the same pale shade next to the busiest one. */
export const heatOpacity = (share: number) => 0.04 + 0.86 * Math.sqrt(share);

/** The cells to draw: [column, row, share], empty cells left out. */
export function heatCells(cells: number[], cols: number): [number, number, number][] {
  return cells.flatMap((v, i) => (v > 0 ? [[i % cols, Math.floor(i / cols), v] as [number, number, number]] : []));
}

export default function Heatmap({ data, side, playerId = null, squads, teamNames }: HeatmapProps) {
  const { prefs, t } = usePrefs();
  const fan = prefs.audience === "fan";
  const player = playerId ? data.players.find((p) => p.player_id === playerId && p.team === side) : undefined;
  const grid = player ?? data.teams[side];
  const name = player ? whoFrom(squads)(player.player_id).name : (teamNames?.[side] ?? t(side === "home" ? "viz.home" : "viz.away"));
  const cw = W / data.cols;
  const ch = H / data.rows;
  const cells = grid ? heatCells(grid.cells, data.cols) : [];
  const legend = fan ? t("viz.heat.legendFan")
    : t(data.source === "frames" ? "viz.heat.legend" : "viz.heat.legendEvents", { n: grid?.samples ?? 0 });
  return (
    <figure className="viz viz-heat">
      <figcaption><b>{t("viz.heat.title")}</b><span className={`viz-side ${side}`}>{name}</span></figcaption>
      <VizPitch label={t("viz.heat.label", { who: name })} arrow
        under={cells.map(([c, r, v]) => (
          <rect key={`${c}-${r}`} className="viz-cell" x={c * cw} y={r * ch} width={cw} height={ch}
            fill={teamColor(side)} fillOpacity={heatOpacity(v)} />
        ))} />
      {cells.length === 0 && <p className="viz-empty">{t("viz.heat.empty")}</p>}
      <p className="viz-note">{legend}</p>
    </figure>
  );
}
