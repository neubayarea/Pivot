// Clips played on the pitch (Ax42): a shot's attack (Ax37) and each key moment (Ax38), played by
// one player (components/ClipPlayer.tsx). A clip is one or more stretches of match time played
// back to back, so a penalty's long wait between the foul and the kick can be skipped.
//
// What each key moment's clip covers, in elapsed seconds:
// - Goal: from the start of the attack (the shot clip's rule: at most 15 s, at least 5 s before)
//   to GOAL_AFTER after it.
// - Red card: KEY_BEFORE before the foul it was shown for to KEY_AFTER after the card.
// - Penalty given: KEY_BEFORE before the foul to KEY_AFTER after it; when the kick goes in, on to
//   GOAL_AFTER after the goal, the wait in between cut when it is longer than GAP_S.
// - VAR reversal: the reviewed goal, penalty or red card as above, and on to KEY_AFTER after the
//   review when that is later (a review more than GAP_S later gets a short stretch of its own).
//
// A set piece's clip (Ax56): SET_BEFORE before the kick, while the players line up, to SET_AFTER
// after the shot, clearance or lost ball that decided it (setpieces.ts, resultOf), or SET_KEPT after
// the kick when nothing did.
import type { MatchEvent } from "@pivot/contracts";
import { goalFor, type KeyKind, type KeyMoment } from "./keyMoments";
import { attackChain, attackFrom, oldestFirst, penaltyKick, type SetPiece, type ShotClip } from "./setpieces";
import { isRedCard, type Side } from "./view";

export const KEY_BEFORE = 8;
export const KEY_AFTER = 3;
export const GOAL_AFTER = 3;
export const GAP_S = 6;
export const SET_BEFORE = 3;
export const SET_AFTER = 3;
export const SET_KEPT = 8;
export { KICK_WITHIN, penaltyKick } from "./setpieces";
export const RATES = [0.25, 0.5, 1, 2, 5] as const;
export type Rate = (typeof RATES)[number];
/** The longest real step the player takes in one go, so a hidden tab or a slow frame does not jump ahead. */
export const MAX_STEP_MS = 100;

export type Part = readonly [number, number];

/** Where a key moment happened on the pitch, marked once the clip reaches it. */
export type ClipMark = { t: number; kind: KeyKind; side: Side; at: readonly [number, number] | null };

export type Clip = {
  parts: Part[];
  /** What happens in the clip, oldest first: drawn (passes and shots) and told in the caption once reached. */
  events: MatchEvent[];
  /** A shot whose ball is flown to its end point; the frames lose it (see clipBall). */
  shot: MatchEvent | null;
  /** Players ringed throughout: who was on the ball, who fouled. */
  involved: string[];
  /** The player named on the pitch from the start: the one sent off, the one who gave the penalty. */
  named: string | null;
  marks: ClipMark[];
};

// --- Clip time ----------------------------------------------------------------------------------
// The player runs on clip time: 0 at the start of the first part, the parts' lengths added up.

export const clipLength = (parts: readonly Part[]) => parts.reduce((s, [a, b]) => s + Math.max(0, b - a), 0);

/** The match second at clip time `c`. */
export function toMatch(parts: readonly Part[], c: number): number {
  let left = Math.max(0, c);
  for (const [a, b] of parts) {
    if (left <= b - a) return a + left;
    left -= b - a;
  }
  return parts.at(-1)?.[1] ?? 0;
}

/** The clip time at match second `t`; a second in a cut gap goes to the start of the next part. */
export function toClip(parts: readonly Part[], t: number): number {
  let c = 0;
  for (const [a, b] of parts) {
    if (t <= b) return c + Math.max(0, t - a);
    c += b - a;
  }
  return c;
}

/** Which part clip time `c` is in. */
export function partAt(parts: readonly Part[], c: number): number {
  let left = c;
  for (let i = 0; i < parts.length; i++) {
    left -= parts[i][1] - parts[i][0];
    if (left < 0) return i;
  }
  return Math.max(0, parts.length - 1);
}

/** Clip time after `dtMs` of real time at `rate`, never past `length`. */
export const advance = (c: number, dtMs: number, rate: number, length: number) =>
  Math.min(length, c + (Math.min(Math.max(0, dtMs), MAX_STEP_MS) / 1000) * rate);

/** The next speed up or down the list, staying at the ends. */
export function nextRate(rate: Rate, by: 1 | -1): Rate {
  const i = RATES.indexOf(rate);
  return RATES[Math.min(RATES.length - 1, Math.max(0, i + by))];
}

// --- The clips ----------------------------------------------------------------------------------

const other = (s: Side): Side => (s === "home" ? "away" : "home");
const loc = (e: MatchEvent) => e.location ?? null;
const players = (events: MatchEvent[]) => [...new Set(events.map((e) => e.player_id).filter((id): id is string => !!id))];

export function fromShot(c: ShotClip): Clip {
  return {
    parts: [[c.from, c.to]], events: c.chain, shot: c.shot, involved: players(c.chain), named: null,
    marks: c.shot.shot_outcome === "goal" ? [{ t: c.shot.t, kind: "goal", side: c.shot.team, at: loc(c.shot) }] : [],
  };
}

/** Everything on the ball, and the fouls and cards, in [from, to]: what a foul's clip tells. */
const around = (all: readonly MatchEvent[], from: number, to: number) =>
  all.filter((e) => e.t >= from && e.t <= to && ["pass", "carry", "dribble", "shot", "foul", "card", "var_review", "goalkeeper"].includes(e.type));

/** A set piece's clip also tells who cleared it or won the ball back. */
const SET_TOLD = new Set<MatchEvent["type"]>(["pass", "carry", "dribble", "shot", "foul", "card", "var_review", "goalkeeper",
  "clearance", "block", "interception", "ball_recovery", "tackle", "offside"]);

/** The clip of a corner, free kick or penalty: the wait before the kick to just after what came of it. */
export function setPieceClip(sp: SetPiece, events: readonly MatchEvent[]): Clip {
  const e = sp.event;
  const by = sp.decidedBy && sp.decidedBy.type !== "period_end" ? sp.decidedBy : null;
  const from = Math.max(0, e.t - SET_BEFORE);
  const to = (by ? by.t : e.t + SET_KEPT) + SET_AFTER;
  const shot = by?.type === "shot" ? by : null;
  return {
    parts: [[from, to]],
    events: oldestFirst(events.filter((x) => x.t >= from && x.t <= to && SET_TOLD.has(x.type))),
    shot: shot?.end_location ? shot : null,
    involved: players(by && by !== e ? [e, by] : [e]),
    named: null,
    marks: shot?.shot_outcome === "goal" ? [{ t: shot.t, kind: "goal", side: shot.team, at: loc(shot) }] : [],
  };
}

function goalClip(all: readonly MatchEvent[], e: MatchEvent, side: Side): Clip {
  const from = attackFrom(all, e, side);
  const chain = attackChain(all, e, from, side);
  const events = chain.includes(e) ? chain : [...chain, e];
  return {
    parts: [[from, e.t + GOAL_AFTER]], events, shot: e.end_location ? e : null, involved: players(chain), named: null,
    marks: [{ t: e.t, kind: "goal", side, at: loc(e) }],
  };
}

/** The foul a card was shown for: the same player's last carded foul up to a minute before. */
function foulFor(all: readonly MatchEvent[], card: MatchEvent): MatchEvent {
  const fouls = all.filter((e) => e.type === "foul" && e.player_id === card.player_id && e.t <= card.t && card.t - e.t <= 60
    && e.seq <= card.seq && isRedCard({ ...e, type: "card" }));
  return fouls.at(-1) ?? card;
}

function redClip(all: readonly MatchEvent[], card: MatchEvent): Clip {
  const foul = foulFor(all, card);
  const from = Math.max(0, foul.t - KEY_BEFORE);
  const to = card.t + KEY_AFTER;
  return {
    parts: [[from, to]], events: around(all, from, to), shot: null, involved: players([foul]), named: foul.player_id,
    marks: [{ t: foul.t, kind: "red", side: card.team, at: loc(foul) ?? loc(card) }],
  };
}

function penaltyClip(all: readonly MatchEvent[], foul: MatchEvent, withKick: boolean): Clip {
  const side = other(foul.team);
  const from = Math.max(0, foul.t - KEY_BEFORE);
  const end = foul.t + KEY_AFTER;
  const kick = withKick ? penaltyKick(all, foul) : null;
  const marks: ClipMark[] = [{ t: foul.t, kind: "penalty", side, at: loc(foul) }];
  if (!kick || kick.shot_outcome !== "goal") {
    return { parts: [[from, end]], events: around(all, from, end), shot: null, involved: players([foul]), named: foul.player_id, marks };
  }
  const to = kick.t + GOAL_AFTER;
  const parts: Part[] = kick.t - GOAL_AFTER - end > GAP_S ? [[from, end], [kick.t - GOAL_AFTER, to]] : [[from, to]];
  const events = parts.flatMap(([a, b]) => around(all, a, b));
  return {
    parts, events, shot: kick, involved: players([foul, kick]), named: foul.player_id,
    marks: [...marks, { t: kick.t, kind: "goal", side, at: loc(kick) }],
  };
}

function reviewedClip(all: readonly MatchEvent[], e: MatchEvent): Clip {
  if (e.type === "shot" || goalFor(e)) return goalClip(all, e, goalFor(e) ?? e.team);
  if (e.type === "foul" && e.foul?.penalty_awarded) return penaltyClip(all, e, false);
  if (e.type === "card" || e.type === "foul") return redClip(all, e);
  const from = Math.max(0, e.t - KEY_BEFORE);
  return { parts: [[from, e.t + KEY_AFTER]], events: around(all, from, e.t + KEY_AFTER), shot: null, involved: players([e]), named: null, marks: [] };
}

/** The clip for one key moment; `events` in any order. */
export function keyClip(k: KeyMoment, events: readonly MatchEvent[]): Clip {
  const all = oldestFirst([...events]);
  switch (k.kind) {
    case "goal":
      return goalClip(all, k.event, k.side);
    case "red":
      return redClip(all, k.event);
    case "penalty":
      return penaltyClip(all, k.event, true);
    case "var": {
      const reviewed = k.event.var ? all.find((e) => e.event_id === k.event.var?.reviewed_event_id) : undefined;
      if (!reviewed) {
        const from = Math.max(0, k.event.t - KEY_BEFORE);
        return { parts: [[from, k.event.t + KEY_AFTER]], events: around(all, from, k.event.t + KEY_AFTER), shot: null, involved: [], named: null,
          marks: [{ t: k.event.t, kind: "var", side: k.side, at: loc(k.event) }] };
      }
      const c = reviewedClip(all, reviewed);
      const last = c.parts.at(-1)!;
      const end = k.event.t + KEY_AFTER;
      const parts: Part[] = end <= last[1] ? c.parts
        : end - last[1] <= GAP_S ? [...c.parts.slice(0, -1), [last[0], end]]
        : [...c.parts, [k.event.t - 1, end]];
      const marks = [...c.marks, { t: k.event.t, kind: "var" as const, side: k.side, at: loc(k.event) ?? loc(reviewed) }];
      return { ...c, parts, marks };
    }
  }
}
