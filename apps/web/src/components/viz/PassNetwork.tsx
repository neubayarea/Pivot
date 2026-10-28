// Pass network (Bx12): one side's starting eleven where they stood with the ball, and a line between
// two players for every pair that completed at least `min_passes` passes to each other. Thicker lines
// mean more passes, bigger dots more passes made and received. Drawn attacking to the right.
// C21 (#401): a fan sees only the five pairs that passed to each other most, with their names; an
// analyst sees every pair with its pass count on the line, and the most involved player ringed
// (data/passNet.ts). The half and the fewest passes for a line are PassNetworkPanel's.
import type { PassNetworkReport } from "@pivot/contracts";
import { FAN_PAIRS, mostInvolved, pairs } from "../../data/passNet";
import type { Side, SquadPlayer } from "../../data/view";
import { usePrefs } from "../../i18n";
import { surname } from "../FocusPickers";
import { VizPitch, teamColor, toPx, whoFrom } from "./pitch";
import "../../styles/viz.css";
import "../../styles/passnet.css";

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
  const all = pairs(team?.edges ?? []).filter((p) => at.has(p.a) && at.has(p.b));
  const shown = fan ? all.slice(0, FAN_PAIRS) : all;
  const inPairs = new Set(shown.flatMap((p) => [p.a, p.b]));
  const most = Math.max(1, ...shown.map((p) => p.passes));
  const central = fan ? null : mostInvolved(team?.nodes ?? []);
  const color = teamColor(side);
  return (
    <figure className={`viz viz-net${fan ? " fan" : ""}`}>
      <figcaption><b>{t("viz.net.title")}</b><span className={`viz-side ${side}`}>{name}</span></figcaption>
      <VizPitch label={t("viz.net.label", { team: name })} arrow>
        {shown.map((p) => {
          const [x1, y1] = toPx(at.get(p.a)!.x, at.get(p.a)!.y);
          const [x2, y2] = toPx(at.get(p.b)!.x, at.get(p.b)!.y);
          const tip = t("viz.net.pair", { a: who(p.a).name, b: who(p.b).name, n: p.passes, ab: p.ab, ba: p.ba });
          return (
            <g key={`${p.a}-${p.b}`} className="viz-pair">
              <line className="viz-edge" x1={x1} y1={y1} x2={x2} y2={y2} stroke={color}
                strokeWidth={1 + 7 * (p.passes / most)} strokeOpacity={0.25 + 0.5 * (p.passes / most)} strokeLinecap="round">
                <title>{tip}</title>
              </line>
              {!fan && (
                <text className="viz-edge-n" x={(x1 + x2) / 2} y={(y1 + y2) / 2 + 4} textAnchor="middle">{p.passes}</text>
              )}
            </g>
          );
        })}
        {team?.nodes.map((n) => {
          const [x, y] = toPx(n.x, n.y);
          const p = who(n.player_id);
          const r = nodeRadius(n.passes + n.received);
          const ring = n.player_id === focus ? "var(--pv-gold)" : n.player_id === central?.player_id ? "var(--pv-ink)" : "var(--pv-paper)";
          const faded = fan && !inPairs.has(n.player_id);
          return (
            <g key={n.player_id} className={`viz-node${n.player_id === focus ? " on" : ""}${faded ? " faded" : ""}${n.player_id === central?.player_id ? " central" : ""}`}>
              <title>{t(fan ? "viz.net.tipFan" : "viz.net.tip", { name: p.name, passes: n.passes, received: n.received })}</title>
              <circle cx={x} cy={y} r={r} fill={color} stroke={ring} strokeWidth={ring === "var(--pv-paper)" ? 2 : 4} />
              <text x={x} y={y + 4.5} textAnchor="middle" fontSize={13} fontWeight={700} fill="var(--pv-paper)">{p.shirt}</text>
              {/* A fan reads the names of the players in the five pairs on the pitch itself. */}
              {fan && inPairs.has(n.player_id) && (
                <text className="viz-net-name" x={x} y={y + r + 14} textAnchor="middle">{surname(p.name)}</text>
              )}
            </g>
          );
        })}
      </VizPitch>
      {!team?.nodes.length && <p className="viz-empty">{t("viz.net.empty")}</p>}
      {fan ? (
        shown.length > 0 && (
          <ol className="viz-pairs">
            {shown.map((p) => (
              <li key={`${p.a}-${p.b}`}>{t("viz.net.pairFan", { a: who(p.a).name, b: who(p.b).name, n: p.passes })}</li>
            ))}
          </ol>
        )
      ) : (
        // names under the pitch: on it they run into each other where the midfield is crowded
        <ol className="viz-names">
          {[...(team?.nodes ?? [])].sort((a, b) => Number(who(a.player_id).shirt) - Number(who(b.player_id).shirt)).map((n) => (
            <li key={n.player_id} className={n.player_id === focus ? "on" : undefined}>
              <b className={`viz-shirt ${side}`}>{who(n.player_id).shirt}</b>{who(n.player_id).name}
            </li>
          ))}
        </ol>
      )}
      {central && (
        <p className="viz-net-central">
          {t("viz.net.central", { name: who(central.player_id).name, n: central.passes + central.received })}
        </p>
      )}
      <p className="viz-note">{fan ? t("viz.net.legendFanTop", { n: FAN_PAIRS }) : t("viz.net.legendPairs", { min: data.min_passes })}</p>
    </figure>
  );
}
