// Set pieces and shot clips (Ax37), worked out in the page from the events and tracking frames the
// board already loads. Coordinates are the pitch's: 105 x 68 m, home attacks to the right all match.
//
// Rules, kept simple on purpose:
// - A set piece is a corner or free-kick pass (`pass_type`), or a shot whose possession began with a
//   free kick and that is that team's first action in it (a direct free kick), or a penalty kick
//   in the match: the kick of a foul that gave one (penaltyKick), or a shot with play_pattern
//   "penalty". A shootout's kicks are not set pieces.
// - Its result follows the next FOLLOW_S seconds: a shot by the taking team is "shot" (or "goal");
//   a clearance, block or keeper claim/punch by the defenders first is "cleared"; the defenders
//   winning the ball any other way (passing, carrying, recovering, intercepting), or the attackers
//   fouling or being offside, is "lost"; nothing of that by the end is "kept".
// - A free kick within SHOOTING_M of the goal it attacks is "shooting" (a direct shot is on); one in
//   the attacking third otherwise is "attacking"; the rest are "deep" and hidden by default.
// - At the kick: who stands in the penalty box. Each attacker in the box (the taker aside) is paired
//   with the nearest free defender (keeper aside), closest pairs first; a pair within MARK_M (a free
//   kick) or CORNER_MARK_M (a corner) is a marker. Fewer than two attackers in the box is too few to say.
// - A free kick: three in five or more attackers marked reads "man", one in three or fewer "zonal", in
//   between "mixed". The simulator marks every attacker in the box there and puts the spare men in a
//   line, so the attackers' share is the measure.
// - A corner (Ax58, #273): the simulator's teams defend it zonal (six zones, two markers), mixed (four
//   zones, markers on the rest) or man (two zones, a marker on every attacker), sim/setpieces.py. A
//   marker stands a metre goal-side of his man; a zonal defender holds a spot within ZONE_DEPTH of the
//   goal line (the posts, the six-yard line, the penalty spot) and marks nobody. Of those two kinds, fewer
//   than ZONAL_MAN zonal reads "man", ZONAL_ZONAL or more "zonal", in between "mixed"; mixed needs two of
//   each. Edge-of-box men (15 m out and more) are neither. Tuned on 12 simulated matches (#273's PR).
// - A free kick's wall: two or more defenders WALL_NEAR–WALL_FAR metres from the ball, within
//   WALL_DEG degrees of the line from the ball to the middle of the goal. The simulator builds its
//   wall 9.15 m off (Ax44, sim/setpieces.py); the wider band also catches a wall still settling.
// Frames are one a second, so "the kick" is the last frame before it and a fast run can be a metre or
// two from where the frame has him.
import type { MatchEvent, TrackingFrame } from "@pivot/contracts";
import type { Side } from "./view";

export const PITCH_L = 105;
export const PITCH_W = 68;
export const FOLLOW_S = 15;
/** How long after a penalty is given its kick is looked for. */
export const KICK_WITHIN = 240;
export const SHOOTING_M = 30;
export const MARK_M = 2.5;
/** A corner's marker: closer than MARK_M, as a zone holder next to an attacker is often within 2.5 m. */
export const CORNER_MARK_M = 1.75;
/** A corner's zonal defenders stand this close to the goal line. */
export const ZONE_DEPTH = 12;
/** Share of zonal defenders among zonal and marking: below ZONAL_MAN man, from ZONAL_ZONAL zonal. */
export const ZONAL_MAN = 0.4;
export const ZONAL_ZONAL = 0.6;
export const WALL_NEAR = 1.5;
export const WALL_FAR = 12;
export const WALL_DEG = 25;
const BOX_DEPTH = 16.5;
const BOX_HALF = 20.15;

export type SetPieceKind = "corner" | "free_kick" | "penalty";
export type SetPieceResult = "goal" | "shot" | "cleared" | "lost" | "kept";
export type FreeKickZone = "shooting" | "attacking" | "deep";

export type SetPiece = {
  event: MatchEvent;
  kind: SetPieceKind;
  /** Free kicks only. */
  zone: FreeKickZone | null;
  result: SetPieceResult;
  /** The event that decided the result: the shot, the clearance, the defender's first touch. */
  decidedBy: MatchEvent | null;
};

const other = (s: Side): Side => (s === "home" ? "away" : "home");
/** x of the goal a team attacks. */
export const goalX = (team: Side) => (team === "home" ? PITCH_L : 0);
/** Distance from the team's own goal line, as the team sees the pitch. */
const fromOwnGoal = (x: number, team: Side) => (team === "home" ? x : PITCH_L - x);

export const oldestFirst = (events: MatchEvent[]) => [...events].sort((a, b) => a.t - b.t || a.seq - b.seq);

const atSpot = (e: MatchEvent, side: Side) =>
  !!e.location && Math.abs(Math.abs(e.location[0] - goalX(side)) - 11) <= 1.5 && Math.abs(e.location[1] - PITCH_W / 2) <= 1.5;

/** The kick of the penalty given for `foul`: the fouled side's next shot, from the spot. `all` is oldest first. */
export function penaltyKick(all: readonly MatchEvent[], foul: MatchEvent): MatchEvent | null {
  const side = other(foul.team);
  const next = all.find((e) => e.type === "shot" && e.team === side && e.t >= foul.t && e.seq > foul.seq && e.t - foul.t <= KICK_WITHIN);
  return next && (next.play_pattern === "penalty" || atSpot(next, side)) ? next : null;
}

export function freeKickZone(e: MatchEvent): FreeKickZone {
  const [x, y] = e.location ?? [PITCH_L / 2, PITCH_W / 2];
  if (Math.hypot(x - goalX(e.team), y - PITCH_W / 2) <= SHOOTING_M) return "shooting";
  return fromOwnGoal(x, e.team) >= (PITCH_L * 2) / 3 ? "attacking" : "deep";
}

const CLEARS = new Set<MatchEvent["type"]>(["clearance", "block"]);
const KEEPER_CLEARS = new Set<MatchEvent["keeper_action"]>(["claim", "punch", "smother", "pick_up", "sweep", "tipped_over", "shot_saved", "shot_parried"]);
const WINS = new Set<MatchEvent["type"]>(["pass", "carry", "dribble", "ball_recovery", "interception", "tackle", "shot"]);

/** What came of the set piece `e`, from the events after it (oldest first). */
export function resultOf(e: MatchEvent, after: MatchEvent[]): Pick<SetPiece, "result" | "decidedBy"> {
  const def = other(e.team);
  if (e.type === "shot") return { result: e.shot_outcome === "goal" ? "goal" : "shot", decidedBy: e };
  for (const x of after) {
    if (x.t > e.t + FOLLOW_S) break;
    if (x.type === "period_end") return { result: "lost", decidedBy: x };
    if (x.team === e.team) {
      if (x.type === "shot") return { result: x.shot_outcome === "goal" ? "goal" : "shot", decidedBy: x };
      if (x.type === "foul" || x.type === "offside") return { result: "lost", decidedBy: x };
      continue;
    }
    if (x.team !== def) continue;
    if (CLEARS.has(x.type) || (x.type === "goalkeeper" && KEEPER_CLEARS.has(x.keeper_action))) return { result: "cleared", decidedBy: x };
    if (WINS.has(x.type)) return { result: "lost", decidedBy: x };
  }
  return { result: "kept", decidedBy: null };
}

/** Every corner, free kick and penalty in the events (any order in, oldest first out). */
export function setPieces(events: MatchEvent[]): SetPiece[] {
  const all = oldestFirst(events);
  const firstOfTeam = new Map<string, MatchEvent>();
  for (const e of all) {
    const k = `${e.possession_id}:${e.team}`;
    if (e.possession_id !== null && !firstOfTeam.has(k)) firstOfTeam.set(k, e);
  }
  const kicks = new Set(all.filter((e) => e.type === "foul" && e.foul?.penalty_awarded).map((f) => penaltyKick(all, f)));
  const out: SetPiece[] = [];
  all.forEach((e, i) => {
    let kind: SetPieceKind | null = null;
    if (e.type === "pass" && (e.pass_type === "corner" || e.pass_type === "free_kick")) kind = e.pass_type;
    else if (e.type === "shot" && e.play_pattern === "free_kick" && firstOfTeam.get(`${e.possession_id}:${e.team}`) === e) kind = "free_kick";
    else if (e.type === "shot" && e.period !== 5 && e.shootout_round == null && (kicks.has(e) || e.play_pattern === "penalty")) kind = "penalty";
    if (!kind) return;
    out.push({ event: e, kind, zone: kind === "free_kick" ? freeKickZone(e) : null, ...resultOf(e, all.slice(i + 1)) });
  });
  return out;
}

export type SetPieceTally = { corners: number; freeKicks: number; penalties: number; shots: number; goals: number };

/** Per team: corners, free kicks shown, penalties, and how many of those ended in a shot or a goal. */
export function tally(list: SetPiece[]): Record<Side, SetPieceTally> {
  const out = {
    home: { corners: 0, freeKicks: 0, penalties: 0, shots: 0, goals: 0 },
    away: { corners: 0, freeKicks: 0, penalties: 0, shots: 0, goals: 0 },
  };
  for (const s of list) {
    const t = out[s.event.team];
    if (s.kind === "corner") t.corners++;
    else if (s.kind === "penalty") t.penalties++;
    else t.freeKicks++;
    if (s.result === "shot" || s.result === "goal") t.shots++;
    if (s.result === "goal") t.goals++;
  }
  return out;
}

// --- Positions at the kick ---------------------------------------------------------------------

type Pos = { player_id: string; x: number; y: number };

export const inBox = (p: { x: number; y: number }, attacking: Side) =>
  Math.abs(p.x - goalX(attacking)) <= BOX_DEPTH && Math.abs(p.y - PITCH_W / 2) <= BOX_HALF;

export type Marking = "man" | "zonal" | "mixed";

export type Setup = {
  attackersInBox: string[];
  defendersInBox: string[];
  /** Attacker id -> the defender paired with him within MARK_M (CORNER_MARK_M on a corner). */
  pairs: [string, string][];
  /** A corner's zonal defenders: near goal, marking nobody. Empty for a free kick. */
  zonal: string[];
  /** null when fewer than two attackers were in the box. */
  marking: Marking | null;
  /** Defenders in the wall, sorted across the pitch; empty for a corner or no wall. */
  wall: string[];
};

/** The frame to read the setup from: the last one before the kick, else the kick's own. */
export function frameBefore(frames: TrackingFrame[], t: number): TrackingFrame | null {
  let best: TrackingFrame | null = null;
  for (const f of frames) if (f.t < t && (!best || f.t > best.t)) best = f;
  return best ?? frames.find((f) => f.t === t) ?? null;
}

export function setupAt(frame: TrackingFrame, sp: SetPiece, isHome: (id: string) => boolean, isKeeper: (id: string) => boolean): Setup {
  const att = sp.event.team;
  const mine = (p: Pos) => isHome(p.player_id) === (att === "home");
  const attackers = frame.players.filter((p) => mine(p) && p.player_id !== sp.event.player_id && inBox(p, att));
  const defenders = frame.players.filter((p) => !mine(p) && inBox(p, att));

  // Closest pairs first, each defender used once.
  const free = defenders.filter((d) => !isKeeper(d.player_id));
  const cand: [number, Pos, Pos][] = [];
  for (const a of attackers) for (const d of free) cand.push([Math.hypot(a.x - d.x, a.y - d.y), a, d]);
  cand.sort((x, y) => x[0] - y[0]);
  const usedA = new Set<string>();
  const usedD = new Set<string>();
  const pairs: [string, string][] = [];
  const corner = sp.kind === "corner";
  const within = corner ? CORNER_MARK_M : MARK_M;
  for (const [dist, a, d] of cand) {
    if (dist > within) break;
    if (usedA.has(a.player_id) || usedD.has(d.player_id)) continue;
    usedA.add(a.player_id);
    usedD.add(d.player_id);
    pairs.push([a.player_id, d.player_id]);
  }
  const zonal = corner ? free.filter((d) => !usedD.has(d.player_id) && Math.abs(d.x - goalX(att)) <= ZONE_DEPTH).map((d) => d.player_id) : [];
  const marking: Marking | null = attackers.length < 2 ? null : corner ? cornerMarking(zonal.length, pairs.length) : freeKickMarking(pairs.length / attackers.length);

  let wall: string[] = [];
  if (sp.kind === "free_kick" && sp.event.location) {
    const [bx, by] = sp.event.location;
    const toGoal = Math.atan2(PITCH_W / 2 - by, goalX(att) - bx);
    const inWall = frame.players.filter((p) => {
      if (mine(p) || isKeeper(p.player_id)) return false;
      const d = Math.hypot(p.x - bx, p.y - by);
      let off = Math.abs(Math.atan2(p.y - by, p.x - bx) - toGoal);
      if (off > Math.PI) off = 2 * Math.PI - off;
      return d >= WALL_NEAR && d <= WALL_FAR && (off * 180) / Math.PI <= WALL_DEG;
    });
    if (inWall.length >= 2) wall = inWall.sort((a, b) => a.y - b.y).map((p) => p.player_id);
  }
  return { attackersInBox: attackers.map((p) => p.player_id), defendersInBox: defenders.map((p) => p.player_id), pairs, zonal, marking, wall };
}

/** A free kick: by the share of the attackers in the box with a marker. */
const freeKickMarking = (share: number): Marking => (share >= 0.6 ? "man" : share <= 1 / 3 ? "zonal" : "mixed");

/** A corner: by the share of zonal defenders among the zonal and the markers; mixed needs two of each. */
export function cornerMarking(zonal: number, marking: number): Marking {
  if (zonal < 2 || marking < 2) return marking >= zonal ? "man" : "zonal";
  const share = zonal / (zonal + marking);
  return share < ZONAL_MAN ? "man" : share >= ZONAL_ZONAL ? "zonal" : "mixed";
}

// --- Shot clips ---------------------------------------------------------------------------------

export type ShotSource = "set_piece" | "open_play" | "counter";

export type ShotClip = {
  shot: MatchEvent;
  source: ShotSource;
  /** Elapsed seconds the clip runs over. */
  from: number;
  to: number;
  /** The shooting team's passes, carries and dribbles in the clip, oldest first, ending with the shot. */
  chain: MatchEvent[];
};

export const CLIP_BEFORE = 15;
export const CLIP_MIN = 5;
export const CLIP_AFTER = 2;
const ON_BALL = new Set<MatchEvent["type"]>(["pass", "carry", "dribble", "shot"]);

/**
 * Where the clip of a shot (or any goal) at `e` starts: the start of the attack (the team's first
 * action in that possession) but no more than CLIP_BEFORE and no less than CLIP_MIN seconds before.
 * `all` is oldest first; `team` is the attacking side (the scorer's, for an own goal).
 */
export function attackFrom(all: readonly MatchEvent[], e: MatchEvent, team: Side = e.team): number {
  const start = all.find((x) => x.team === team && x.possession_id !== null && x.possession_id === e.possession_id && x.t <= e.t)?.t ?? e.t;
  return Math.max(0, Math.max(e.t - CLIP_BEFORE, Math.min(start, e.t - CLIP_MIN)));
}

/** The team's passes, carries and dribbles from `from` up to the shot `e`, ending with it. */
export function attackChain(all: readonly MatchEvent[], e: MatchEvent, from: number, team: Side = e.team): MatchEvent[] {
  return all.filter((x) => x.team === team && ON_BALL.has(x.type) && x.t >= from && (x.t < e.t || x === e) && x.seq <= e.seq);
}

/**
 * One clip per shot, oldest first: from attackFrom() to CLIP_AFTER after the shot. A shot is from a
 * set piece if its possession began with a corner, free kick or penalty, or a corner or free kick by
 * the same team came in the same possession just before.
 */
export function shotClips(events: MatchEvent[], end = Infinity): ShotClip[] {
  const all = oldestFirst(events);
  const pieces = setPieces(all);
  return all.filter((e) => e.type === "shot").map((shot) => {
    const from = attackFrom(all, shot);
    const to = Math.min(end, shot.t + CLIP_AFTER);
    const piece = pieces.some((p) => p.event.team === shot.team && p.event.possession_id === shot.possession_id
      && p.event.t <= shot.t && shot.t - p.event.t <= FOLLOW_S);
    const source: ShotSource = piece || shot.play_pattern === "corner" || shot.play_pattern === "free_kick" || shot.play_pattern === "penalty"
      ? "set_piece" : shot.play_pattern === "counter" ? "counter" : "open_play";
    return { shot, source, from, to, chain: attackChain(all, shot, from) };
  });
}

/** Every player and the ball at fractional second `t`, moved in a straight line between the frames either side. */
export function frameBetween(frames: TrackingFrame[], t: number): TrackingFrame | null {
  if (!frames.length) return null;
  let i = 0;
  while (i < frames.length - 1 && frames[i + 1].t <= t) i++;
  const a = frames[i];
  const b = frames[i + 1];
  if (!b || t <= a.t) return a;
  const k = Math.min(1, (t - a.t) / (b.t - a.t));
  const mix = (p: number, q: number) => p + (q - p) * k;
  const next = new Map(b.players.map((p) => [p.player_id, p]));
  return {
    ...a,
    t,
    ball: { ...a.ball, x: mix(a.ball.x, b.ball.x), y: mix(a.ball.y, b.ball.y), z: mix(a.ball.z, b.ball.z), owner_id: k < 0.5 ? a.ball.owner_id : b.ball.owner_id },
    // A player in only one of the two frames (on or off between them) stays where that frame has him.
    players: a.players.map((p) => {
      const q = next.get(p.player_id);
      return q ? { ...p, x: mix(p.x, q.x), y: mix(p.y, q.y) } : p;
    }),
  };
}

/**
 * The ball as a clip draws it at `t`: from the second before the shot it flies from where the
 * frames had it to the shot's end point and stays there. The frames cannot be used for that last
 * stretch: after a goal they already have the ball back on the centre spot in the shot's second.
 */
export function clipBall(shot: MatchEvent, frames: TrackingFrame[], t: number): { x: number; y: number } | null {
  const end = shot.end_location;
  const start = shot.t - 1;
  if (!end || t < start) return null;
  const from = frameBetween(frames, start)?.ball ?? { x: end[0], y: end[1] };
  const k = Math.min(1, t - start);
  return { x: from.x + (end[0] - from.x) * k, y: from.y + (end[1] - from.y) * k };
}
