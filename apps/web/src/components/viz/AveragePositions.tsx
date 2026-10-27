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
  /** C18: the starting XIs. Given, the starters are always drawn and the substitutes only on a switch,
   *  smaller and hollow, nudged off any dot they would cover. */
  starters?: ReadonlySet<string>;
  /** C18: each starter's slot in the formation on paper, in metres in the team's own half-frame
   *  (attacking to the right), drawn as a faint ring joined to where the player actually stood. */
  ghosts?: ReadonlyMap<string, readonly [number, number]>;
};

export default function AveragePositions({ data, squads, teamNames, phase: start = "in_possession", minSeconds = 1800,
                                           focus = null, starters, ghosts }: AveragePositionsProps) {
  const { t } = usePrefs();
  const [phase, setPhase] = useState<Phase>(start);
  const [subs, setSubs] = useState(false);
  const who = whoFrom(squads);
  const names = teamNames ?? { home: t("viz.home"), away: t("viz.away") };
  const isSub = (id: string) => !!starters && !starters.has(id);
  const shown = data.players.filter((p) => p[phase] && (starters
    ? starters.has(p.player_id) || (subs && p.seconds >= minSeconds)
    : p.seconds >= minSeconds));
  // Where each dot goes. With the line-ups given (C18), a dot that would cover one already placed
  // moves down until it is clear, starters first, so no number hides behind another.
  const at = new Map<string, [number, number]>();
  for (const p of [...shown].sort((a, b) => Number(isSub(a.player_id)) - Number(isSub(b.player_id)))) {
    let [x, y] = toPx(p[phase]!.x, p[phase]!.y, p.team === "away");
    for (let tries = 0; starters && tries < 4 && [...at.values()].some(([ox, oy]) => Math.hypot(x - ox, y - oy) < 20); tries++) y += 20;
    at.set(p.player_id, [x, y]);
  }
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
      {starters && (
        <label className="viz-subs">
          <input type="checkbox" checked={subs} onChange={(e) => setSubs(e.target.checked)} /> {t("viz.pos.subs")}
        </label>
      )}
      <VizPitch label={t("viz.pos.label", { home: names.home, away: names.away })}>
        {ghosts && shown.filter((p) => ghosts.has(p.player_id)).map((p) => {
          const [gx, gy] = ghosts.get(p.player_id)!;
          const [x0, y0] = toPx(gx, gy, p.team === "away");
          const [x, y] = at.get(p.player_id)!;
          return (
            <g key={`g-${p.player_id}`} className="viz-ghost" aria-hidden="true">
              <line x1={x0} y1={y0} x2={x} y2={y} stroke={teamColor(p.team)} />
              <circle cx={x0} cy={y0} r={9} stroke={teamColor(p.team)} />
            </g>
          );
        })}
        {shown.map((p) => {
          const [x, y] = at.get(p.player_id)!;
          const w = who(p.player_id);
          if (isSub(p.player_id)) {
            return (
              <g key={p.player_id} className="viz-node sub">
                <title>{w.name}</title>
                <circle cx={x} cy={y} r={8} fill="var(--pv-paper)" stroke={teamColor(p.team)} strokeWidth={2} />
                <text x={x} y={y + 3.5} textAnchor="middle" fontSize={9} fontWeight={700} fill={teamColor(p.team)}>{w.shirt}</text>
              </g>
            );
          }
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
        {ghosts && <span className="viz-ghost-key">{t("viz.pos.ghostKey")}</span>}
      </p>
    </figure>
  );
}
