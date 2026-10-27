// Team shape on the pitch board (Ax36): who plays where at a second, the lines a formation is drawn
// with, and three numbers for how a team stands. Back line and width follow the StatCalculator
// (pivot_core/analytics/stats.py, MET-016 and MET-017): back line is the defenders' mean distance
// from their own goal, width the spread of the outfield players across the pitch. Depth (front to
// back of the outfield players) is the compactness number. Unlike the StatCalculator these are
// taken over every frame, in and out of possession, so one frame has a value too.
import type { MatchEvent, TeamSheet, TeamTactics, TrackingFrame } from "@pivot/contracts";
import type { Side } from "../data/view";
import { PITCH } from "../fixtures/pivot-detail";

export type Role = TeamSheet["starters"][number]["role"];
export type Line = "GK" | "DF" | "MF" | "AM" | "FW";

const LINES: Record<Role, Line> = {
  GK: "GK", LB: "DF", CB: "DF", RB: "DF", LWB: "DF", RWB: "DF",
  DM: "MF", CM: "MF", LM: "MF", RM: "MF", AM: "AM", LW: "FW", RW: "FW", ST: "FW",
};
export const lineOf = (role: Role | undefined): Line | undefined => (role ? LINES[role] : undefined);

export type Lineup = {
  /** Role of every player on a sheet at that second, starters and those who came on. */
  roles: Map<string, Role>;
  formation: Record<Side, string>;
};

/** The team sheets in force at second `t`: the starting ones, then each event that carries a new one. */
export function lineupAt(sheets: Record<Side, TeamSheet>, events: MatchEvent[], t: number): Lineup {
  const now = { ...sheets };
  // events are newest first; walk them oldest first so the latest sheet wins.
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.t <= t && e.team_sheet) now[e.team] = e.team_sheet;
  }
  const roles = new Map<string, Role>();
  for (const side of ["home", "away"] as const) for (const s of now[side].starters) roles.set(s.player_id, s.role);
  return { roles, formation: { home: now.home.formation, away: now.away.formation } };
}

/** Each team's tactics in force at second `t` (Ax67): the coach's plan, then each event that carries new ones. */
export function tacticsAt(start: Record<Side, TeamTactics>, events: MatchEvent[], t: number): Record<Side, TeamTactics> {
  const now = { ...start };
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.t <= t && e.tactics) now[e.team] = e.tactics;
  }
  return now;
}

export type Shape = { backLine: number; width: number; depth: number };

type Point = { player_id: string; x: number; y: number };

/** x from the team's own goal line, as the StatCalculator's attacking view: home attacks to the right. */
const fromGoal = (x: number, side: Side) => (side === "home" ? x : PITCH.length - x);

function shapeOf(players: Point[], roles: Map<string, Role>): Shape | null {
  const out = players.filter((p) => roles.get(p.player_id) !== "GK");
  if (out.length < 2) return null;
  const xs = out.map((p) => p.x);
  const ys = out.map((p) => p.y);
  const backs = out.filter((p) => lineOf(roles.get(p.player_id)) === "DF").map((p) => p.x);
  return {
    backLine: backs.length ? backs.reduce((a, b) => a + b, 0) / backs.length : NaN,
    width: Math.max(...ys) - Math.min(...ys),
    depth: Math.max(...xs) - Math.min(...xs),
  };
}

const sideOf = (frame: TrackingFrame, side: Side, isHome: (id: string) => boolean) =>
  frame.players.filter((p) => isHome(p.player_id) === (side === "home"))
    .map((p) => ({ player_id: p.player_id, x: fromGoal(p.x, side), y: p.y }));

/** One team's shape in one frame; null when it has fewer than two outfield players in it. */
export const frameShape = (frame: TrackingFrame, side: Side, roles: Map<string, Role>, isHome: (id: string) => boolean) =>
  shapeOf(sideOf(frame, side, isHome), roles);

/** The mean of each number over some frames; null when no frame had a shape. */
export function meanShape(frames: TrackingFrame[], side: Side, roles: Map<string, Role>, isHome: (id: string) => boolean): Shape | null {
  const sum = { backLine: 0, width: 0, depth: 0 };
  let n = 0;
  let nBack = 0;
  for (const f of frames) {
    const s = frameShape(f, side, roles, isHome);
    if (!s) continue;
    n++;
    sum.width += s.width;
    sum.depth += s.depth;
    if (!Number.isNaN(s.backLine)) {
      nBack++;
      sum.backLine += s.backLine;
    }
  }
  return n ? { backLine: nBack ? sum.backLine / nBack : NaN, width: sum.width / n, depth: sum.depth / n } : null;
}

/**
 * The formation lines to draw for one team, in pitch metres: defenders, midfielders, attacking
 * midfielders and forwards, each joined across the pitch. A line of one player draws nothing.
 */
export function shapeLines(frame: TrackingFrame, side: Side, roles: Map<string, Role>, isHome: (id: string) => boolean): [number, number][][] {
  const groups = new Map<Line, [number, number][]>();
  for (const p of frame.players) {
    if (isHome(p.player_id) !== (side === "home")) continue;
    const line = lineOf(roles.get(p.player_id));
    if (!line || line === "GK") continue;
    groups.set(line, [...(groups.get(line) ?? []), [p.x, p.y]]);
  }
  return [...groups.values()].filter((g) => g.length > 1).map((g) => g.sort((a, b) => a[1] - b[1]));
}

/** Back line height as an x on the pitch, for drawing it as a line across. */
export const backLineX = (s: Shape, side: Side) => (side === "home" ? s.backLine : PITCH.length - s.backLine);
