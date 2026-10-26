import type { CSSProperties, ReactNode } from "react";
import type { MatchEvent, TrackingFrame } from "@pivot/contracts";
import { involves, type Side, type SquadPlayer } from "../data/view";
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
  /** Side and shirt number of each player; without it, ids like the fixture's "hcy-11" are read. */
  who?: (id: string) => Who;
  /** How long the dots glide to the next frame; the time between frames, so motion looks continuous. */
  stepMs?: number;
  /** The player picked on the board (Ax36): a ring and a label with his name. */
  picked?: string | null;
  /** Tapping or clicking a dot picks that player; tapping him again lets go. */
  onPick?: (id: string | null) => void;
  /** Players in the event just shown, drawn with a dashed gold ring. */
  marked?: ReadonlySet<string>;
  /** Text for a player's label and tooltip, e.g. "9 · Name · ST". */
  tag?: (id: string) => string;
  /** Drawn under the players: the team-shape layer (Ax36). */
  under?: ReactNode;
  /** Drawn over everything: a clip's marks (Ax42). */
  over?: ReactNode;
};

export type Who = { home: boolean; shirt: string };

// The fixture's ids are "<club>-<shirt>", Harbour City's club code "hcy".
const fromId = (id: string) => ({ home: id.startsWith("hcy"), shirt: id.slice(id.lastIndexOf("-") + 1) });
/** `who` for tracking frames, whose ids (sim ids like "h01") are looked up in the squads. */
export function whoFromSquads(squads: Record<Side, SquadPlayer[]>): (id: string) => Who {
  const map = new Map<string, Who>();
  for (const side of ["home", "away"] as const) {
    for (const p of squads[side]) map.set(p.player_id, { home: side === "home", shirt: p.shirt === null ? "" : String(p.shirt) });
  }
  return (id) => map.get(id) ?? { home: id.startsWith("h"), shirt: "" };
}

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

export default function Pitch({ frame, actions, selected, label, focus = null, who = fromId, stepMs,
  picked = null, onPick, marked, tag, under, over }: Props) {
  const ball = px([frame.ball.x, frame.ball.y]);
  const style = stepMs ? ({ "--pv-step": `${Math.round(stepMs)}ms` } as CSSProperties) : undefined;
  // The ball carrier's ring is the board's (onPick); the detail page marks its evidence instead.
  const carrier = onPick ? frame.ball.owner_id : null;
  const pickedAt = picked ? frame.players.find((p) => p.player_id === picked) : undefined;
  return (
    <svg className="pitch" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} style={style}>
      <Markings />
      {under}
      {actions.filter((e) => e.event_id !== selected).map((e) => <Action key={e.event_id} e={e} on={false} mine={involves(e, focus)} />)}
      {frame.players.map((p) => {
        const { home, shirt } = who(p.player_id);
        const followed = p.player_id === focus;
        const ring = p.player_id === picked ? "picked" : marked?.has(p.player_id) ? "marked" : p.player_id === carrier ? "carrier" : "";
        return (
          <g key={p.player_id} className={`pl${followed ? " followed" : ""}${ring ? ` ${ring}` : ""}${onPick ? " pick" : ""}`}
            style={{ transform: `translate(${p.x * S}px, ${p.y * S}px)` }} data-player={p.player_id}
            onClick={onPick ? () => onPick(p.player_id === picked ? null : p.player_id) : undefined}>
            {tag && <title>{tag(p.player_id)}</title>}
            {onPick && <circle r={16} fill="transparent" />}
            {followed && <circle r={14} fill="none" stroke="var(--pv-gold)" strokeWidth={3} />}
            {ring === "picked" && <circle r={15} fill="none" stroke="var(--pv-ink)" strokeWidth={3} />}
            {ring === "marked" && <circle r={14} fill="none" stroke="var(--pv-gold)" strokeWidth={3} strokeDasharray="5 3" />}
            {ring === "carrier" && <circle r={13} fill="none" stroke="var(--pv-sheet)" strokeWidth={2.5} />}
            <circle r={9} fill={home ? "var(--pv-home)" : "var(--pv-away)"} stroke={followed ? "var(--pv-gold)" : "var(--pv-ink)"} strokeWidth={followed ? 3 : 2} />
            <text y={4} fontSize={10} fontWeight={700} textAnchor="middle" fill="var(--pv-sheet)">
              {shirt}
            </text>
          </g>
        );
      })}
      <g className="pl" style={{ transform: `translate(${ball[0] + 8}px, ${ball[1] - 8}px)` }}>
        <circle r={4} fill="var(--pv-sheet)" stroke="var(--pv-ink)" strokeWidth={1.5} />
      </g>
      {actions.filter((e) => e.event_id === selected).map((e) => <Action key={e.event_id} e={e} on mine={involves(e, focus)} />)}
      {over}
      {pickedAt && tag && <Label x={pickedAt.x * S} y={pickedAt.y * S} text={tag(pickedAt.player_id)} />}
    </svg>
  );
}

/** The picked player's name above his dot, kept inside the pitch. */
function Label({ x, y, text }: { x: number; y: number; text: string }) {
  const w = Math.min(W - 8, text.length * 7 + 14);
  const cx = Math.min(W - w / 2 - 4, Math.max(w / 2 + 4, x));
  const cy = y < 40 ? y + 32 : y - 28;
  return (
    <g className="pl-label" pointerEvents="none">
      <rect x={cx - w / 2} y={cy - 11} width={w} height={22} fill="var(--pv-sheet)" stroke="var(--pv-ink)" strokeWidth={2} />
      <text x={cx} y={cy + 4.5} fontSize={13} fontWeight={700} textAnchor="middle" fill="var(--pv-ink)">{text}</text>
    </g>
  );
}
