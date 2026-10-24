import type { MatchEvent, TrackingFrame } from "@pivot/contracts";
import { involves } from "../data/view";
import { PITCH } from "../fixtures/pivot-detail";

// 105 x 68 m at 5 px per metre, same drawing as "06 S2" in the design spec. Home attacks to the right.
const S = 5;
const W = PITCH.length * S;
const H = PITCH.width * S;
const LINE = { fill: "none", stroke: "var(--pv-pitch-line)", strokeWidth: 2 };

type Props = {
  frame: TrackingFrame;
  /** Evidence actions to draw at this second; `selected` gets the ring and its #tag. */
  actions: MatchEvent[];
  selected: string | null;
  label: string;
  /** The followed player (C08): gold outline on his dot, a gold ring on actions he took part in. */
  focus?: string | null;
};

const shirt = (id: string) => id.slice(id.lastIndexOf("-") + 1);
const px = ([x, y]: [number, number]) => [x * S, y * S] as const;

function Markings() {
  return (
    <>
      <rect x={0} y={0} width={W} height={H} fill="var(--pv-pitch)" />
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

function Action({ e, on, mine }: { e: MatchEvent; on: boolean; mine: boolean }) {
  if (!e.location) return null;
  const [x1, y1] = px(e.location);
  const tag = `#${e.seq}`;
  let arrow = null;
  if (e.end_location) {
    const [x2, y2] = px(e.end_location);
    const a = Math.atan2(y2 - y1, x2 - x1);
    const tip = (d: number, s: number) => `${x2 - d * Math.cos(a) + s * Math.sin(a)},${y2 - d * Math.sin(a) - s * Math.cos(a)}`;
    arrow = (
      <>
        <line x1={x1} y1={y1} x2={x2 - 8 * Math.cos(a)} y2={y2 - 8 * Math.sin(a)} stroke="var(--pv-gold)"
          strokeWidth={on ? 5 : 3} strokeDasharray={e.type === "pass" || e.type === "shot" ? undefined : "7 4"} />
        <polygon points={`${x2},${y2} ${tip(13, 7)} ${tip(13, -7)}`} fill="var(--pv-gold)" stroke="var(--pv-ink)" strokeWidth={1.5} />
      </>
    );
  }
  return (
    <g className={`act${on ? " on" : ""}${mine ? " mine" : ""}`}>
      {arrow}
      {mine && !on && <circle cx={x1} cy={y1} r={13} fill="none" stroke="var(--pv-gold)" strokeWidth={3} strokeDasharray="5 3" />}
      {on && (
        <>
          <circle cx={x1} cy={y1} r={15} fill="none" stroke="var(--pv-gold)" strokeWidth={3} />
          <g transform={`translate(${Math.min(W - 30, Math.max(30, x1))}, ${Math.max(22, y1 - 31)})`}>
            <rect x={-26} y={-9} width={52} height={18} fill="var(--pv-gold)" stroke="var(--pv-ink)" strokeWidth={1.5} />
            <text y={4} fontSize={12} fontWeight={700} textAnchor="middle" fill="var(--pv-on-gold)">
              {tag}
            </text>
          </g>
        </>
      )}
    </g>
  );
}

export default function Pitch({ frame, actions, selected, label, focus = null }: Props) {
  const ball = px([frame.ball.x, frame.ball.y]);
  return (
    <svg className="pitch" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <Markings />
      {actions.filter((e) => e.event_id !== selected).map((e) => <Action key={e.event_id} e={e} on={false} mine={involves(e, focus)} />)}
      {frame.players.map((p) => {
        const home = p.player_id.startsWith("hcy");
        const followed = p.player_id === focus;
        return (
          <g key={p.player_id} className={`pl${followed ? " followed" : ""}`} style={{ transform: `translate(${p.x * S}px, ${p.y * S}px)` }}>
            {followed && <circle r={14} fill="none" stroke="var(--pv-gold)" strokeWidth={3} />}
            <circle r={9} fill={home ? "var(--pv-home)" : "var(--pv-away)"} stroke={followed ? "var(--pv-gold)" : "var(--pv-ink)"} strokeWidth={followed ? 3 : 2} />
            <text y={4} fontSize={10} fontWeight={700} textAnchor="middle" fill="var(--pv-sheet)">
              {shirt(p.player_id)}
            </text>
          </g>
        );
      })}
      <g className="pl" style={{ transform: `translate(${ball[0] + 8}px, ${ball[1] - 8}px)` }}>
        <circle r={4} fill="var(--pv-sheet)" stroke="var(--pv-ink)" strokeWidth={1.5} />
      </g>
      {actions.filter((e) => e.event_id === selected).map((e) => <Action key={e.event_id} e={e} on mine={involves(e, focus)} />)}
    </svg>
  );
}
