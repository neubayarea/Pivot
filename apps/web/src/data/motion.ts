// Smooth motion between the once-a-second tracking frames (Ax61). The pitch is redrawn on every
// screen frame from the frames around the clock: players on a Catmull-Rom curve through the four
// nearest frames, so they do not change speed with a jolt at each whole second; the ball on a
// straight line (it flies straight), or on its carrier's feet while one player has it.
import type { MatchEvent, TrackingFrame } from "@pivot/contracts";
import { isRedCard } from "./view";

export type Pose = {
  t: number;
  players: Map<string, readonly [number, number]>;
  ball: readonly [number, number];
  owner: string | null;
};

/** Index of the last frame at or before `t` (0 if `t` is earlier); frames are in t order. */
export function indexAt(frames: readonly TrackingFrame[], t: number): number {
  let lo = 0;
  let hi = frames.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (frames[mid].t <= t) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

const catmull = (p0: number, p1: number, p2: number, p3: number, k: number) =>
  0.5 * (2 * p1 + (-p0 + p2) * k + (2 * p0 - 5 * p1 + 4 * p2 - p3) * k * k + (-p0 + 3 * p1 - 3 * p2 + p3) * k * k * k);

const clampPitch = (x: number, y: number) => [Math.min(106, Math.max(-1, x)), Math.min(69, Math.max(-1, y))] as const;

/** Where everyone is at `t`, from frames in t order that include the ones around it. */
export function poseAt(frames: readonly TrackingFrame[], t: number): Pose | null {
  if (!frames.length) return null;
  const i = indexAt(frames, t);
  const a = frames[i];
  const b = frames[i + 1];
  // Past either end, or a gap of more than a few seconds (a new chunk, half time): no gliding across it.
  if (!b || t <= a.t || b.t - a.t > 3) {
    return { t, players: new Map(a.players.map((p) => [p.player_id, [p.x, p.y] as const])), ball: [a.ball.x, a.ball.y], owner: a.ball.owner_id };
  }
  const k = Math.min(1, (t - a.t) / (b.t - a.t));
  const prev = frames[i - 1] && a.t - frames[i - 1].t <= 3 ? frames[i - 1] : a;
  const next = frames[i + 2] && frames[i + 2].t - b.t <= 3 ? frames[i + 2] : b;
  const find = (f: TrackingFrame, id: string) => f.players.find((p) => p.player_id === id);
  const bs = new Map(b.players.map((p) => [p.player_id, p]));
  const players = new Map<string, readonly [number, number]>();
  for (const p of a.players) {
    const q = bs.get(p.player_id);
    // A player in only one of the two frames (on or off between them) stays where that frame has him.
    if (!q) {
      players.set(p.player_id, [p.x, p.y]);
      continue;
    }
    const o = find(prev, p.player_id) ?? p;
    const r = find(next, p.player_id) ?? q;
    players.set(p.player_id, clampPitch(catmull(o.x, p.x, q.x, r.x, k), catmull(o.y, p.y, q.y, r.y, k)));
  }
  const owner = a.ball.owner_id && a.ball.owner_id === b.ball.owner_id ? a.ball.owner_id : null;
  const feet = owner ? players.get(owner) : undefined;
  const ball = feet ?? ([a.ball.x + (b.ball.x - a.ball.x) * k, a.ball.y + (b.ball.y - a.ball.y) * k] as const);
  return { t, players, ball, owner: owner ?? (k < 0.5 ? a.ball.owner_id : b.ball.owner_id) };
}

/** The pose at `t` with the players averaged over `w` seconds either side (fast replays); the ball is left sharp. */
export function smoothPose(frames: readonly TrackingFrame[], t: number, w: number): Pose | null {
  const mid = poseAt(frames, t);
  if (!mid || w <= 0) return mid;
  const side = [poseAt(frames, t - w), poseAt(frames, t + w)];
  const players = new Map<string, readonly [number, number]>();
  for (const [id, [x, y]] of mid.players) {
    let sx = 2 * x;
    let sy = 2 * y;
    let n = 2;
    for (const p of side) {
      const q = p?.players.get(id);
      if (q) {
        sx += q[0];
        sy += q[1];
        n++;
      }
    }
    players.set(id, [sx / n, sy / n]);
  }
  return { ...mid, players, ball: mid.owner && players.get(mid.owner) ? players.get(mid.owner)! : mid.ball };
}

/** The ball's path over the last `span` seconds up to `t`, oldest first, for a short trail. */
export function ballTrail(frames: readonly TrackingFrame[], t: number, span = 1.2, steps = 8): [number, number][] {
  if (!frames.length) return [];
  const out: [number, number][] = [];
  for (let s = steps; s >= 0; s--) {
    const at = t - (span * s) / steps;
    if (at < frames[0].t) continue;
    const i = indexAt(frames, at);
    const a = frames[i];
    const b = frames[i + 1];
    const k = b && b.t - a.t <= 3 ? Math.min(1, Math.max(0, (at - a.t) / (b.t - a.t))) : 0;
    out.push(b ? [a.ball.x + (b.ball.x - a.ball.x) * k, a.ball.y + (b.ball.y - a.ball.y) * k] : [a.ball.x, a.ball.y]);
  }
  return out;
}

/** The trail from its last jump on (a restart puts the ball back on a spot): two points `max` metres apart are not one flight. */
export function trimJumps(pts: readonly (readonly [number, number])[], max = 12): (readonly [number, number])[] {
  let from = 0;
  for (let i = 1; i < pts.length; i++) if (Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) > max) from = i;
  return pts.slice(from);
}

// --- Event cues ---------------------------------------------------------------------------------

export type CueKind = "pass" | "shot" | "goal" | "tackle" | "foul" | "yellow" | "red";

export type Cue = {
  id: string;
  kind: CueKind;
  team: MatchEvent["team"];
  t: number;
  from: readonly [number, number];
  to: readonly [number, number] | null;
};

/** A pass, shot, tackle, foul or card as a cue on the pitch; null for anything else or with no place. */
export function cueOf(e: MatchEvent): Cue | null {
  if (!e.location) return null;
  const base = { id: e.event_id, team: e.team, t: e.t, from: e.location, to: e.end_location ?? null };
  switch (e.type) {
    case "pass":
      return e.end_location ? { ...base, kind: "pass" } : null;
    case "shot":
      return { ...base, kind: e.shot_outcome === "goal" ? "goal" : "shot" };
    case "tackle":
    case "interception":
    case "block":
      return { ...base, kind: "tackle", to: null };
    case "foul":
      return { ...base, kind: "foul", to: null };
    case "card":
      return { ...base, kind: isRedCard(e) ? "red" : "yellow", to: null };
    default:
      return null;
  }
}

/** How long a cue stays up, in match seconds: a few seconds, longer when the replay runs fast so it is still seen. */
export const cueSpan = (speed: number) => Math.min(30, Math.max(2.5, speed * 1.5));

/** The cues to draw at `now`: events in the last `span` seconds, newest last, at most `max` of them (goals and cards kept longer). */
export function cuesAt(events: readonly MatchEvent[], now: number, span: number, max = 4): Cue[] {
  const out: Cue[] = [];
  for (const e of events) {
    if (e.t > now) continue;
    const long = e.type === "card" || (e.type === "shot" && e.shot_outcome === "goal");
    if (now - e.t > (long ? Math.max(span, 6) : span)) continue;
    const c = cueOf(e);
    if (c) out.push(c);
  }
  return out.sort((a, b) => a.t - b.t).slice(-max);
}

// --- Scrolling ----------------------------------------------------------------------------------

/** Scrolling that follows the viewer's "reduce motion" setting (C11): a jump instead of a glide. */
export const scrollBehavior = (): ScrollBehavior =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";

/** The page's language for numbers ("1,000", "1.000"), from <html lang> (C11); English outside a browser. */
export const numberLocale = (): string =>
  (typeof document !== "undefined" && document.documentElement.lang) || "en";
