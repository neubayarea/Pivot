// Average positions (Bx12): both teams on one pitch, home attacking to the right and away to the
// left, each player where they stood on average with the ball or without it (a switch above).
import { useState } from "react";
import type { AveragePositionsReport } from "@pivot/contracts";
import type { Side, SquadPlayer } from "../../data/view";
import { usePrefs } from "../../i18n";
import { VizPitch, teamColor, toPx, whoFrom } from "./pitch";
import "../../styles/viz.css";

export type Phase = "in_possession" | "out_of_possession";

export type AveragePositionsProps = {
  data: AveragePositionsReport;
  squads?: Record<Side, SquadPlayer[]>;
  teamNames?: Record<Side, string>;
  /** Start on this phase; the viewer can switch. */
  phase?: Phase;
  /** Leave out players on for less than this many seconds (default 30 minutes): a substitute's dot
   *  would sit on top of the player he replaced and say little. */
  minSeconds?: number;
  focus?: string | null;
};

export default function AveragePositions({ data, squads, teamNames, phase: start = "in_possession", minSeconds = 1800,
                                           focus = null }: AveragePositionsProps) {
  const { t } = usePrefs();
  const [phase, setPhase] = useState<Phase>(start);
  const who = whoFrom(squads);
  const names = teamNames ?? { home: t("viz.home"), away: t("viz.away") };
  const shown = data.players.filter((p) => p.seconds >= minSeconds && p[phase]);
  return (
    <figure className="viz viz-pos">
      <figcaption>
        <b>{t("viz.pos.title")}</b>
        <span className="viz-switch" role="group" aria-label={t("viz.pos.title")}>
          {(["in_possession", "out_of_possession"] as const).map((p) => (
            <button key={p} type="button" aria-pressed={phase === p} onClick={() => setPhase(p)}>
              {t(p === "in_possession" ? "viz.pos.with" : "viz.pos.without")}
            </button>
          ))}
        </span>
      </figcaption>
      <VizPitch label={t("viz.pos.label", { home: names.home, away: names.away })}>
        {shown.map((p) => {
          const pt = p[phase]!;
          const [x, y] = toPx(pt.x, pt.y, p.team === "away");
          const w = who(p.player_id);
          return (
            <g key={p.player_id} className={`viz-node${p.player_id === focus ? " on" : ""}`}>
              <title>{w.name}</title>
              <circle cx={x} cy={y} r={11} fill={teamColor(p.team)}
                stroke={p.player_id === focus ? "var(--pv-gold)" : "var(--pv-paper)"} strokeWidth={p.player_id === focus ? 4 : 2} />
              <text x={x} y={y + 4.5} textAnchor="middle" fontSize={12} fontWeight={700} fill="var(--pv-paper)">{w.shirt}</text>
            </g>
          );
        })}
      </VizPitch>
      {shown.length === 0 && <p className="viz-empty">{t("viz.pos.empty")}</p>}
      <p className="viz-note viz-sides">
        <span className="viz-side home">{names.home}</span>
        <span className="viz-side away">{names.away}</span>
        <span>{t("viz.pos.legend")}</span>
      </p>
    </figure>
  );
}
