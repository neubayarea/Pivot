// Per-second positions for the S2 pitch, generated around each demo-1021 pivot.
// A stand-in for the simulator's TrackingFrame feed (ADR-0014): every player has a slot in
// the team shape, the block slides with momentum and sways with the ball side, and evidence
// events get their pitch coordinates from where the actor stands at that second.
import type { Claim, MatchEvent, MinuteMetric, Pivot1 as Pivot, PlayerPosition, TrackingFrame } from "@pivot/contracts";

type Side = "home" | "away";

/** One row of the S2 before/after table; both cells carry the stat_ref they were read from. */
export type BeforeAfterRow = { label: string; before: Claim; after: Claim };

export type PivotDetailData = {
  /** Match seconds the pitch timeline covers. */
  window: [number, number];
  /** One frame per second over `window`, inclusive. */
  frames: TrackingFrame[];
  beforeAfter: BeforeAfterRow[];
};

export const PITCH = { length: 105, width: 68 } as const;

// Slots in the home team's frame (attacking x = 105). Away mirrors them.
const SHAPES: Record<string, Record<string, [number, number]>> = {
  "hcy-433": {
    "hcy-1": [5, 34], "hcy-3": [22, 58], "hcy-4": [20, 41], "hcy-5": [20, 27], "hcy-6": [22, 10],
    "hcy-8": [40, 22], "hcy-14": [38, 40], "hcy-10": [50, 32],
    "hcy-11": [62, 56], "hcy-17": [62, 56], "hcy-9": [66, 34], "hcy-7": [60, 12],
  },
  // From the 73:20 tactical shift: back three, wing-backs pushed on.
  "hcy-343": {
    "hcy-1": [5, 34], "hcy-4": [19, 46], "hcy-5": [17, 34], "hcy-6": [19, 22],
    "hcy-3": [40, 61], "hcy-8": [36, 26], "hcy-14": [36, 42], "hcy-7": [40, 7],
    "hcy-10": [56, 34], "hcy-17": [62, 54], "hcy-9": [66, 32],
  },
  "nvr-442": {
    "nvr-1": [5, 34], "nvr-2": [20, 10], "nvr-5": [18, 27], "nvr-6": [18, 41], "nvr-3": [20, 58],
    "nvr-7": [40, 8], "nvr-4": [36, 28], "nvr-8": [36, 42], "nvr-11": [40, 60],
    "nvr-10": [56, 30], "nvr-9": [58, 40],
  },
  // Ten men after the 37:52 red card: Castro drops into the back line, one striker.
  "nvr-441": {
    "nvr-1": [5, 34], "nvr-2": [20, 10], "nvr-4": [18, 28], "nvr-6": [18, 41], "nvr-3": [20, 58],
    "nvr-7": [38, 10], "nvr-8": [34, 30], "nvr-10": [36, 42], "nvr-11": [38, 58], "nvr-9": [56, 34],
  },
};

const SHIFT_AT = 73 * 60 + 20;
const RED_AT = 37 * 60 + 52;
const shapeOf = (team: Side, t: number) =>
  team === "home" ? SHAPES[t >= SHIFT_AT ? "hcy-343" : "hcy-433"] : SHAPES[t >= RED_AT ? "nvr-441" : "nvr-442"];

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const round = (v: number) => Math.round(v * 10) / 10;
// A fixed per-player phase so each one sways differently but identically on every load.
const phase = (id: string) => [...id].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 997, 7) / 997 * Math.PI * 2;

function momentumAt(metrics: MinuteMetric[], t: number): number {
  const m = t / 60;
  const a = metrics[Math.min(metrics.length - 1, Math.floor(m))];
  const b = metrics[Math.min(metrics.length - 1, Math.floor(m) + 1)];
  return a.momentum + (b.momentum - a.momentum) * (m - Math.floor(m));
}

function position(team: Side, id: string, t: number, momentum: number): [number, number] {
  const [bx, by] = shapeOf(team, t)[id] ?? [52.5, 34];
  const keeper = id.endsWith("-1");
  const p = phase(id);
  // The block steps up when its side has the momentum and drops when it does not.
  const push = (team === "home" ? momentum : -momentum) * 9;
  // Everyone drifts towards the ball side together, outfielders more than the keeper.
  const ballSide = 7 * Math.sin(t / 37);
  const ownX = keeper ? bx + push * 0.2 : bx + push + 3 * Math.sin(t / 11 + p) + 1.5 * Math.sin(t / 5.3 + p * 2);
  const ownY = by + (keeper ? 0.3 : 1) * ballSide + 2.5 * Math.sin(t / 13 + p * 3);
  const x = team === "home" ? ownX : PITCH.length - ownX;
  return [round(clamp(x, 1, PITCH.length - 1)), round(clamp(ownY, 1, PITCH.width - 1))];
}

type Inputs = {
  matchId: string;
  events: MatchEvent[];
  metrics: MinuteMetric[];
  pivots: Pivot[];
  /** Players on the pitch at second t, keepers included. */
  onPitch: (team: Side, t: number) => string[];
  beforeAfter: Record<string, BeforeAfterRow[]>;
};

/** Frames for [from, to], plus evidence events placed on the pitch where their actors stand. */
export function buildPivotDetails({ matchId, events, metrics, pivots, onPitch, beforeAfter }: Inputs) {
  const byId = new Map(events.map((e) => [e.event_id, e]));
  const details: Record<string, PivotDetailData> = {};

  for (const pv of pivots) {
    const ids = new Set([...pv.trigger_event_ids, ...(pv.narrative?.sentences.flatMap((s) => s.evidence_ids) ?? [])]);
    const times = [...ids].map((id) => byId.get(id)!.t);
    const from = Math.min(pv.minute * 60 - 300, Math.floor(Math.min(...times) / 60 - 1) * 60);
    const to = Math.min(90 * 60, Math.max(pv.minute * 60 + 300, Math.ceil(Math.max(...times) / 60 + 1) * 60));

    // Pull each evidence actor (and pass receiver) to a spot that fits the event's third,
    // easing in and out over a few seconds so the dots never jump.
    const anchors = new Map<string, { t: number; x: number; y: number }[]>();
    const anchor = (team: Side, id: string, t: number, own: [number, number]) => {
      const x = team === "home" ? own[0] : PITCH.length - own[0];
      anchors.set(id, [...(anchors.get(id) ?? []), { t, x, y: own[1] }]);
    };
    for (const id of ids) {
      const e = byId.get(id)!;
      if (!e.player_id || !e.third) continue;
      const [, by] = shapeOf(e.team, e.t)[e.player_id] ?? [0, 34];
      const n = e.seq % 7;
      const x = e.type === "shot" ? 88 + n : { defensive: 20, middle: 46, final: 78 }[e.third] + n * 2;
      const own: [number, number] = e.pass_type === "corner" ? [104, e.meta.side === "left" ? 2 : 66]
        : [x, e.type === "shot" ? 30 + n : by];
      anchor(e.team, e.player_id, e.t, own);
      if (e.type === "pass" && e.receiver_id) {
        const [, ry] = shapeOf(e.team, e.t)[e.receiver_id] ?? [0, 34];
        anchor(e.team, e.receiver_id, e.t + 2, e.pass_type === "corner" ? [96, 30 + n] : [Math.min(100, own[0] + 14), ry]);
      }
    }
    const EASE = 8;
    const pulled = (id: string, t: number, [x, y]: [number, number]): [number, number] => {
      for (const a of anchors.get(id) ?? []) {
        const d = Math.abs(t - a.t);
        if (d >= EASE) continue;
        const w = 0.5 + 0.5 * Math.cos((d / EASE) * Math.PI);
        return [round(x + (a.x - x) * w), round(y + (a.y - y) * w)];
      }
      return [x, y];
    };

    const frames: TrackingFrame[] = [];
    let prev = new Map<string, [number, number]>();
    for (let t = from; t <= to; t++) {
      const momentum = momentumAt(metrics, t);
      const players: PlayerPosition[] = [];
      const now = new Map<string, [number, number]>();
      for (const team of ["home", "away"] as const) {
        for (const id of onPitch(team, t)) {
          const [x, y] = pulled(id, t, position(team, id, t, momentum));
          const last = prev.get(id);
          now.set(id, [x, y]);
          // Fitness falls over the match; Rossi comes on fresh at 62:40.
          const since = id === "hcy-17" ? t - (62 * 60 + 40) : t;
          players.push({
            player_id: id, x, y,
            speed_ms: last ? round(Math.min(12, Math.hypot(x - last[0], y - last[1]))) : 0,
            fitness: Math.round((1 - 0.35 * clamp(since / 5400, 0, 1)) * 100) / 100,
          });
        }
      }
      prev = now;
      // The ball sits with whoever made the latest on-ball event in the last few seconds.
      let last: MatchEvent | undefined;
      for (let i = events.length - 1; i >= 0 && !last; i--) {
        const e = events[i];
        if (e.t <= t && e.player_id && now.has(e.player_id)) last = e;
      }
      const owner = last && t - last.t <= 4 ? last.player_id : null;
      const [bx, by] = (last?.player_id && now.get(last.player_id)) || [PITCH.length / 2, PITCH.width / 2];
      frames.push({
        match_id: matchId, t, period: t < 45 * 60 ? 1 : 2, possession: last?.team ?? null,
        ball: { x: bx, y: by, z: 0, owner_id: owner }, players,
      });
    }

    const at = (id: string | null, t: number) => {
      const f = frames[clamp(t - from, 0, frames.length - 1)];
      const p = f.players.find((q) => q.player_id === id);
      return p ? ([p.x, p.y] as [number, number]) : null;
    };
    for (const id of ids) {
      const e = byId.get(id)!;
      if (e.location || !e.player_id) continue;
      // Players sent off or substituted are gone from the frame at e.t, so look one second earlier.
      const start = at(e.player_id, e.t) ?? at(e.player_id, e.t - 1);
      if (!start) continue;
      const dir = e.team === "home" ? 1 : -1;
      const ahead: [number, number] = [round(clamp(start[0] + 12 * dir, 1, 104)), start[1]];
      e.location = start;
      if (e.type === "pass") e.end_location = at(e.receiver_id, e.t + 2) ?? ahead;
      else if (e.type === "shot") e.end_location = [dir > 0 ? PITCH.length : 0, 34 + (e.t % 5) - 2];
      else if (e.type === "pressure") {
        const opp = frames[e.t - from].players.filter((p) => !p.player_id.startsWith(e.team === "home" ? "hcy" : "nvr"));
        const near = opp.reduce((a, b) => (Math.hypot(b.x - start[0], b.y - start[1]) < Math.hypot(a.x - start[0], a.y - start[1]) ? b : a));
        e.end_location = [near.x, near.y];
      } else if (e.type === "substitution" || e.type === "card") {
        e.end_location = [PITCH.length / 2, PITCH.width];
      } else if (e.type === "duel" || e.type === "carry" || e.type === "tackle") e.end_location = ahead;
    }

    details[pv.pivot_id] = { window: [from, to], frames, beforeAfter: beforeAfter[pv.pivot_id] ?? [] };
  }
  return details;
}

/** Average momentum (home positive) over whole minutes [a, b), as a before/after row cell. */
export function momentumAvg(metrics: MinuteMetric[], window: [number, number]): Claim {
  const ms = metrics.filter((m) => m.minute >= window[0] && m.minute < window[1]);
  const value = Math.round((ms.reduce((s, m) => s + m.momentum, 0) / (ms.length || 1)) * 100) / 100;
  return { stat_ref: { metric: "momentum_avg", team: "home", player_id: null, window }, unit: "index", value };
}
