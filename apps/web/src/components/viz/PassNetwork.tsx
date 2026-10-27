// Pass network (Bx12): one side's starting eleven where they stood with the ball, and a line between
// two players for every pair that completed at least `min_passes` passes to each other. Thicker lines
// mean more passes, bigger dots more passes made and received. Drawn attacking to the right.
import type { PassNetworkReport } from "@pivot/contracts";
import type { Side, SquadPlayer } from "../../data/view";
import { usePrefs } from "../../i18n";
import { VizPitch, teamColor, toPx, whoFrom } from "./pitch";
import "../../styles/viz.css";

export type PassNetworkProps = {
  data: PassNetworkReport;
  side: Side;
  squads?: Record<Side, SquadPlayer[]>;
  teamNames?: Record<Side, string>;
  /** A player to ring, e.g. the one followed. */
  focus?: string | null;
};

export const nodeRadius = (touches: number) => 9 + 1.3 * Math.sqrt(touches);

export default function PassNetwork({ data, side, squads, teamNames, focus = null }: PassNetworkProps) {
  const { prefs, t } = usePrefs();
  const fan = prefs.audience === "fan";
  const who = whoFrom(squads);
  const team = data.teams[side];
  const name = teamNames?.[side] ?? t(side === "home" ? "viz.home" : "viz.away");
  const at = new Map(team?.nodes.map((n) => [n.player_id, n]) ?? []);
  const most = Math.max(1, ...(team?.edges.map((e) => e.passes) ?? []));
  const color = teamColor(side);
  return (
    <figure className="viz viz-net">
      <figcaption><b>{t("viz.net.title")}</b><span className={`viz-side ${side}`}>{name}</span></figcaption>
      <VizPitch label={t("viz.net.label", { team: name })} arrow>
        {team?.edges.map((e) => {
          const a = at.get(e.from_id);
          const b = at.get(e.to_id);
          if (!a || !b) return null;
          const [x1, y1] = toPx(a.x, a.y);
          const [x2, y2] = toPx(b.x, b.y);
          return (
            <line key={`${e.from_id}-${e.to_id}`} className="viz-edge" x1={x1} y1={y1} x2={x2} y2={y2} stroke={color}
              strokeWidth={1 + 7 * (e.passes / most)} strokeOpacity={0.25 + 0.5 * (e.passes / most)} strokeLinecap="round">
              <title>{t("viz.net.edge", { from: who(e.from_id).name, to: who(e.to_id).name, n: e.passes })}</title>
            </line>
          );
        })}
        {team?.nodes.map((n) => {
          const [x, y] = toPx(n.x, n.y);
          const p = who(n.player_id);
          const r = nodeRadius(n.passes + n.received);
          return (
            <g key={n.player_id} className={`viz-node${n.player_id === focus ? " on" : ""}`}>
              <title>{t(fan ? "viz.net.tipFan" : "viz.net.tip", { name: p.name, passes: n.passes, received: n.received })}</title>
              <circle cx={x} cy={y} r={r} fill={color} stroke={n.player_id === focus ? "var(--pv-gold)" : "var(--pv-paper)"}
                strokeWidth={n.player_id === focus ? 4 : 2} />
              <text x={x} y={y + 4.5} textAnchor="middle" fontSize={13} fontWeight={700} fill="var(--pv-paper)">{p.shirt}</text>
            </g>
          );
        })}
      </VizPitch>
      {!team?.nodes.length && <p className="viz-empty">{t("viz.net.empty")}</p>}
      {/* names under the pitch: on it they run into each other where the midfield is crowded */}
      <ol className="viz-names">
        {[...(team?.nodes ?? [])].sort((a, b) => Number(who(a.player_id).shirt) - Number(who(b.player_id).shirt)).map((n) => (
          <li key={n.player_id} className={n.player_id === focus ? "on" : undefined}>
            <b className={`viz-shirt ${side}`}>{who(n.player_id).shirt}</b>{who(n.player_id).name}
          </li>
        ))}
      </ol>
      <p className="viz-note">{fan ? t("viz.net.legendFan") : t("viz.net.legend", { min: data.min_passes })}</p>
    </figure>
  );
}
