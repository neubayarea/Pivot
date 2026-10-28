// The analyst's pitch overlays on the Replay / Live board (C21, #401), drawn under the players from
// the frames and events the page already has, up to the clock (live or replayed).
//  - Shape band: each team's outfield block at this second (deepest to highest, touchline to
//    touchline), the box the shape table's width and depth measure, faint in kit colour.
//  - Pressing zones: the pressures, tackles and interceptions of the last five minutes as a soft
//    density in kit colour; the count of pressures is the same one the pressures stat counts.
//  - Passing lanes: completed passes of the last three minutes, grouped zone to zone, as arrows whose
//    width is the count; progressive passes (the StatCalculator's ATTR-011 rule) stand out.
// Home attacks to the right in the data (the StatCalculator's attacking view), so no flipping here.
import type { MatchEvent, TrackingFrame } from "@pivot/contracts";
import type { Side } from "../../data/view";
import type { Role } from "../shape";

const S = 5;
const LENGTH = 105, WIDTH = 68;
export const PRESS_WINDOW = 5 * 60;
export const PASS_WINDOW = 3 * 60;
const PRESS_TYPES = new Set(["pressure", "tackle", "interception"]);

const colour = (side: Side) => (side === "home" ? "var(--pv-home)" : "var(--pv-away)");

/** The pressures, tackles and interceptions with a place, in the `span` seconds up to `now`. */
export function pressEvents(events: readonly MatchEvent[], now: number, span = PRESS_WINDOW): MatchEvent[] {
  return events.filter((e) => PRESS_TYPES.has(e.type) && e.location && e.t <= now && e.t > now - span);
}

/** A pass the passes stat counts (not a throw-in) that found a team-mate, with both ends known. */
export const completedPass = (e: MatchEvent) => e.type === "pass" && e.pass_type !== "throw_in" && e.outcome === "success" && !!e.location && !!e.end_location;

/**
 * The StatCalculator's progressive pass (ATTR-011, Wyscout's thresholds by half of the pitch), the
 * same rule as `StatCalculator.progressive` in pivot_core: the distance to goal must fall by 30 m
 * inside the own half, 15 m into the other half, 10 m inside it.
 */
export function progressive(e: MatchEvent): boolean {
  if ((e.type !== "pass" && e.type !== "carry") || e.outcome !== "success" || !e.location || !e.end_location) return false;
  if (e.pass_type === "corner" || e.pass_type === "throw_in") return false;
  const view = ([x, y]: readonly [number, number]): [number, number] => (e.team === "home" ? [x, y] : [LENGTH - x, WIDTH - y]);
  const s = view(e.location), f = view(e.end_location);
  const toGoal = ([x, y]: [number, number]) => Math.hypot(LENGTH - x, WIDTH / 2 - y);
  const gain = toGoal(s) - toGoal(f);
  const half = LENGTH / 2;
  if (s[0] < half && f[0] < half) return gain >= 30;
  if (s[0] < half && f[0] >= half) return gain >= 15;
  return gain >= 10;
}

const COLS = 6, ROWS = 4;
const zoneOf = ([x, y]: readonly [number, number]) => {
  const c = Math.min(COLS - 1, Math.max(0, Math.floor((x / LENGTH) * COLS)));
  const r = Math.min(ROWS - 1, Math.max(0, Math.floor((y / WIDTH) * ROWS)));
  return [c, r] as const;
};
const centre = ([c, r]: readonly [number, number]) => [((c + 0.5) * LENGTH) / COLS, ((r + 0.5) * WIDTH) / ROWS] as const;

export type Lane = { side: Side; from: readonly [number, number]; to: readonly [number, number]; n: number; progressive: number };

/** Completed passes of the last `span` seconds, zone to zone (6 × 4 zones), with how many were progressive. */
export function passLanes(events: readonly MatchEvent[], now: number, span = PASS_WINDOW): Lane[] {
  const lanes = new Map<string, Lane>();
  for (const e of events) {
    if (e.t > now || e.t <= now - span || !completedPass(e)) continue;
    const a = zoneOf(e.location!), b = zoneOf(e.end_location!);
    if (a[0] === b[0] && a[1] === b[1]) continue;
    const key = `${e.team}:${a}:${b}`;
    const lane = lanes.get(key) ?? { side: e.team, from: centre(a), to: centre(b), n: 0, progressive: 0 };
    lane.n += 1;
    if (progressive(e)) lane.progressive += 1;
    lanes.set(key, lane);
  }
  return [...lanes.values()];
}

/** Each team's outfield block at this second: deepest to highest player, touchline to touchline. */
export function blockOf(frame: TrackingFrame, side: Side, roles: Map<string, Role>, isHome: (id: string) => boolean) {
  const pts = frame.players.filter((p) => isHome(p.player_id) === (side === "home") && roles.get(p.player_id) !== "GK");
  if (pts.length < 3) return null;
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
  return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
}

export function ShapeBands({ frame, roles, isHome }: { frame: TrackingFrame; roles: Map<string, Role>; isHome: (id: string) => boolean }) {
  return (
    <g className="ov-band" pointerEvents="none">
      {(["home", "away"] as const).map((side) => {
        const b = blockOf(frame, side, roles, isHome);
        return b && <rect key={side} x={b.x0 * S} y={b.y0 * S} width={(b.x1 - b.x0) * S} height={(b.y1 - b.y0) * S} rx={10}
          fill={colour(side)} fillOpacity={0.1} stroke={colour(side)} strokeOpacity={0.35} strokeDasharray="6 6" />;
      })}
    </g>
  );
}

export function PressingZones({ events, now, id }: { events: readonly MatchEvent[]; now: number; id: string }) {
  const press = pressEvents(events, now);
  return (
    <g className="ov-press" pointerEvents="none">
      <defs><filter id={`${id}-blur`} x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation={18} /></filter></defs>
      {(["home", "away"] as const).map((side) => (
        <g key={side} filter={`url(#${id}-blur)`} opacity={0.85}>
          {press.filter((e) => e.team === side).map((e) => (
            <circle key={e.event_id} cx={e.location![0] * S} cy={e.location![1] * S} r={7 * S} fill={colour(side)} fillOpacity={0.3} />
          ))}
        </g>
      ))}
    </g>
  );
}

export function PassingLanes({ events, now, id }: { events: readonly MatchEvent[]; now: number; id: string }) {
  const lanes = passLanes(events, now);
  const top = Math.max(1, ...lanes.map((l) => l.n));
  return (
    <g className="ov-lanes" pointerEvents="none">
      <defs>
        {(["home", "away"] as const).map((side) => (
          <marker key={side} id={`${id}-${side}`} viewBox="0 0 10 10" refX={6} refY={5} markerWidth={16} markerHeight={16} markerUnits="userSpaceOnUse" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 Z" fill={colour(side)} />
          </marker>
        ))}
      </defs>
      {lanes.sort((a, b) => a.progressive - b.progressive || a.n - b.n).map((l, i) => {
        const [x1, y1] = l.from, [x2, y2] = l.to;
        // Stop short of the zone centre so the arrowhead sits clear of the next lane.
        const k = 0.86;
        return (
          <line key={i} x1={x1 * S} y1={y1 * S} x2={(x1 + (x2 - x1) * k) * S} y2={(y1 + (y2 - y1) * k) * S}
            stroke={colour(l.side)} strokeWidth={2 + (l.n / top) * 8} strokeOpacity={l.progressive ? 0.85 : 0.22} strokeLinecap="round"
            markerEnd={`url(#${id}-${l.side})`} />
        );
      })}
    </g>
  );
}
