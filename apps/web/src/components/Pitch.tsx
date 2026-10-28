import type { CSSProperties, ReactNode, Ref } from "react";
import type { MatchEvent, TrackingFrame } from "@pivot/contracts";
import { involves, useMaybeMatch, type Side, type SquadPlayer } from "../data/view";
import { usePrefs } from "../i18n";
import { PITCH } from "../fixtures/pivot-detail";

// 105 x 68 m at 5 px per metre, same drawing as "06 S2" in the design spec. Home attacks to the right.
const S = 5;
const W = PITCH.length * S;
const H = PITCH.width * S;
/** The drawing's width over height, for a placeholder that holds its place (Ax79). */
export const PITCH_RATIO = W / H;
const LINE = { fill: "none", stroke: "var(--pv-pitch-line)", strokeWidth: 2 };

type Props = {
  frame: TrackingFrame;
  /** Evidence actions to draw at this second; `selected` gets the ring and its #tag. */
  actions: MatchEvent[];
  selected: string | null;
  label: string;
  /**
   * The followed player (C08, Ax92): a bigger dot with a gold ring and his surname always shown, the others
   * a little faded; a gold ring on actions he took part in. Left out, it is the viewer's ★ player.
   */
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
  /** Drawn over the players, under the ball: a clip's marks (Ax42), the event cues (Ax61). */
  over?: ReactNode;
  /** Ax61: the dots, the ball and its trail are moved on every screen frame by usePitchMotion, not by React. */
  animated?: boolean;
  svgRef?: Ref<SVGSVGElement>;
  /** Extra classes on the svg, e.g. "paused" to hold the cues' fade. */
  className?: string;
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

/** "D. Sahaltessen" → "Sahaltessen": the followed player's label on the pitch. */
export const surname = (name: string) => name.trim().split(/\s+/).at(-1) ?? name;

export default function Pitch({ frame, actions, selected, label, focus: focusProp, who = fromId, stepMs,
  picked = null, onPick, marked, tag, under, over, animated = false, svgRef, className }: Props) {
  const { prefs } = usePrefs();
  const view = useMaybeMatch();
  const focus = focusProp === undefined ? (prefs.focus_player_id ?? null) : focusProp;
  const focusAt = focus ? frame.players.find((p) => p.player_id === focus) : undefined;
  const focusName = focus && view ? surname(view.playerName(focus)) : "";
  const ball = px([frame.ball.x, frame.ball.y]);
  const style = stepMs && !animated ? ({ "--pv-step": `${Math.round(stepMs)}ms` } as CSSProperties) : undefined;
  // The ball carrier's ring is the board's (onPick); the detail page marks its evidence instead.
  const carrier = onPick ? frame.ball.owner_id : null;
  const pickedAt = picked ? frame.players.find((p) => p.player_id === picked) : undefined;
  // The followed player is drawn last but for the picked one, so nobody covers him.
  const top = [focusAt, animated ? pickedAt : undefined].filter((p) => p !== undefined);
  const order = [...frame.players.filter((p) => !top.includes(p)), ...top];
  return (
    <svg className={`pitch${animated ? " anim" : ""}${focusAt ? " following" : ""}${className ? ` ${className}` : ""}`} viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={label} style={style} ref={svgRef}>
      <Markings />
      {under}
      {actions.filter((e) => e.event_id !== selected).map((e) => <Action key={e.event_id} e={e} on={false} mine={involves(e, focus)} />)}
      {order.map((p) => {
        const { home, shirt } = who(p.player_id);
        const followed = p.player_id === focus;
        const ring = p.player_id === picked ? "picked" : marked?.has(p.player_id) ? "marked" : p.player_id === carrier ? "carrier" : "";
        return (
          <g key={p.player_id} className={`pl${followed ? " followed" : ""}${ring ? ` ${ring}` : ""}${onPick ? " pick" : ""}`}
            style={animated ? undefined : { transform: `translate(${p.x * S}px, ${p.y * S}px)` }} data-player={p.player_id}
            onClick={onPick ? () => onPick(p.player_id === picked ? null : p.player_id) : undefined}>
            {tag && <title>{tag(p.player_id)}</title>}
            {onPick && <circle r={16} fill="transparent" />}
            {followed && (
              <>
                <circle className="follow-pulse" r={19} fill="none" stroke="var(--pv-gold)" strokeWidth={3} />
                <circle r={18} fill="none" stroke="var(--pv-ink)" strokeWidth={7} />
                <circle r={18} fill="none" stroke="var(--pv-gold)" strokeWidth={4} />
              </>
            )}
            {ring === "picked" && <circle r={15} fill="none" stroke="var(--pv-ink)" strokeWidth={3} />}
            {ring === "marked" && <circle r={14} fill="none" stroke="var(--pv-ink)" strokeWidth={2.5} strokeDasharray="5 3" />}
            {ring === "carrier" && (
              <>
                <circle r={14} fill="none" stroke="var(--pv-ink)" strokeWidth={6} />
                <circle r={14} fill="none" stroke="var(--pv-sheet)" strokeWidth={3} />
              </>
            )}
            <circle r={followed ? 12 : 9} fill={home ? "var(--pv-home)" : "var(--pv-away)"} stroke="var(--pv-ink)" strokeWidth={2} />
            <text y={followed ? 4.5 : 4} fontSize={followed ? 12 : 10} fontWeight={700} textAnchor="middle" fill="var(--pv-sheet)">
              {shirt}
            </text>
            {followed && focusName && p !== pickedAt && <FollowTag name={focusName} x={p.x * S} />}
            {/* Moving with its dot, the picked player's name rides inside the group when animated. */}
            {animated && p === pickedAt && tag && <Label x={p.x * S} y={p.y * S} text={tag(p.player_id)} relative />}
          </g>
        );
      })}
      {actions.filter((e) => e.event_id === selected).map((e) => <Action key={e.event_id} e={e} on mine={involves(e, focus)} />)}
      {over}
      {/* Ax61: the ball last, over everything, with a short trail behind it. */}
      {animated && <polyline className="ball-trail" data-trail="" pointerEvents="none" fill="none" />}
      <g className="pl" data-ball="" pointerEvents="none"
        style={animated ? undefined : { transform: `translate(${ball[0] + 8}px, ${ball[1] - 8}px)` }}>
        <circle r={7} fill="none" stroke="var(--pv-ink)" strokeOpacity={0.35} strokeWidth={4} />
        <circle r={5} fill="var(--pv-ball)" stroke="var(--pv-ink)" strokeWidth={2} />
      </g>
      {!animated && pickedAt && tag && <Label x={pickedAt.x * S} y={pickedAt.y * S} text={tag(pickedAt.player_id)} />}
    </svg>
  );
}

/** The followed player's surname next to his dot, on whichever side has room; it moves with the dot. */
function FollowTag({ name, x }: { name: string; x: number }) {
  const w = name.length * 7.4 + 14;
  const left = x > W - w - 30;
  const x0 = left ? -24 - w : 24;
  return (
    <g className="follow-tag" pointerEvents="none">
      <rect x={x0} y={-11} width={w} height={22} rx={11} fill="var(--pv-gold)" stroke="var(--pv-ink)" strokeWidth={1.5} />
      <text x={x0 + w / 2} y={4.5} fontSize={13} fontWeight={700} textAnchor="middle" fill="var(--pv-on-gold)">★ {name}</text>
    </g>
  );
}

/** The picked player's name above his dot, kept inside the pitch; `relative` draws it from the dot's own origin. */
function Label({ x, y, text, relative = false }: { x: number; y: number; text: string; relative?: boolean }) {
  const w = Math.min(W - 8, text.length * 7 + 14);
  const cx = Math.min(W - w / 2 - 4, Math.max(w / 2 + 4, x));
  const cy = y < 40 ? y + 32 : y - 28;
  return (
    <g className="pl-label" pointerEvents="none" transform={relative ? `translate(${-x} ${-y})` : undefined}>
      <rect x={cx - w / 2} y={cy - 11} width={w} height={22} fill="var(--pv-sheet)" stroke="var(--pv-ink)" strokeWidth={2} />
      <text x={cx} y={cy + 4.5} fontSize={13} fontWeight={700} textAnchor="middle" fill="var(--pv-ink)">{text}</text>
    </g>
  );
}
