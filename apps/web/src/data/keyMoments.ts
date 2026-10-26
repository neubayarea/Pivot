// The match's key moments (Ax38): goals, red cards, penalties given and VAR reversals, taken
// straight from the events. Pivots only follow the momentum line, so a goal on its own never
// makes one; these are shown beside the pivots, not instead of them. Scores follow QA-005:
// a shot with outcome "goal" (a goal VAR ruled out is "disallowed"), plus own goals.
import type { MatchEvent } from "@pivot/contracts";
import { isRedCard, type Side } from "./view";

export type KeyKind = "goal" | "red" | "penalty" | "var";
/** What a goal did to the score, from the scorer's side. */
export type GoalSituation =
  | "opener" | "equaliser" | "lateEqualiser" | "stoppageEqualiser"
  | "lead" | "comeback" | "winner" | "extend" | "pullBack";

export type KeyMoment = {
  event: MatchEvent;
  kind: KeyKind;
  /** The scorer, the side awarded the penalty, the side sent off, or the side whose goal, penalty or red VAR took away. */
  side: Side;
  /** Goals only: the score straight after it, what it did to the score, and how it was scored. */
  score?: { home: number; away: number };
  situation?: GoalSituation;
  penalty?: boolean;
  ownGoal?: boolean;
};

const other = (s: Side): Side => (s === "home" ? "away" : "home");

/** The last five minutes of normal or extra time, stoppage included. */
const late = (e: MatchEvent) => (e.period === 2 && e.period_t >= 40 * 60) || (e.period === 4 && e.period_t >= 10 * 60);
const stoppage = (e: MatchEvent) => (e.period === 2 && e.period_t >= 45 * 60) || (e.period === 4 && e.period_t >= 15 * 60);

/** The side a goal counts for, or null when the event is not a goal (shoot-outs left out). */
export function goalFor(e: MatchEvent): Side | null {
  if (e.period === 5) return null;
  if (e.type === "shot" && e.shot_outcome === "goal") return e.team;
  if (e.meta?.own_goal === "true") return other(e.team);
  return null;
}

/**
 * Key moments in match order. `finished` lets a late go-ahead goal that nobody answered be the
 * winner; while the match is on it is only a lead or a comeback.
 */
export function keyMoments(events: readonly MatchEvent[], finished: boolean): KeyMoment[] {
  const byTime = [...events].sort((a, b) => a.t - b.t || a.seq - b.seq);
  const byId = new Map(byTime.map((e) => [e.event_id, e]));
  const goals = byTime.filter((e) => goalFor(e));
  const lastGoal = goals.at(-1);
  const score = { home: 0, away: 0 };
  const trailed = { home: false, away: false };
  const out: KeyMoment[] = [];
  for (const e of byTime) {
    if (e.period === 5) continue;
    const scorer = goalFor(e);
    if (scorer) {
      const before = score[scorer] - score[other(scorer)];
      const total = score.home + score.away;
      score[scorer]++;
      const after = before + 1;
      let situation: GoalSituation;
      if (after === 0) situation = stoppage(e) ? "stoppageEqualiser" : late(e) ? "lateEqualiser" : "equaliser";
      else if (after === 1 && finished && late(e) && e === lastGoal) situation = "winner";
      else if (total === 0) situation = "opener";
      else if (after === 1) situation = trailed[scorer] ? "comeback" : "lead";
      else if (after > 1) situation = "extend";
      else situation = "pullBack";
      if (score.home < score.away) trailed.home = true;
      if (score.away < score.home) trailed.away = true;
      out.push({
        event: e, kind: "goal", side: scorer, score: { ...score }, situation,
        penalty: e.play_pattern === "penalty", ownGoal: e.type !== "shot",
      });
    } else if (isRedCard(e)) {
      out.push({ event: e, kind: "red", side: e.team });
    } else if (e.type === "foul" && e.foul?.penalty_awarded) {
      out.push({ event: e, kind: "penalty", side: other(e.team) });
    } else if (e.type === "var_review" && e.var?.decision === "overturned") {
      // The side whose goal, penalty or red card it was: a penalty belongs to the side fouled.
      const reviewed = byId.get(e.var.reviewed_event_id);
      const side = reviewed ? (e.var.review_of === "penalty" ? other(reviewed.team) : reviewed.team) : e.team;
      out.push({ event: e, kind: "var", side });
    }
  }
  return out;
}

/** Elapsed seconds a pivot's evidence covers; the five minutes either side when its window is not known. */
export type Window = readonly [number, number];
export const pivotWindow = (minute: number, window?: Window | null): Window => window ?? [(minute - 5) * 60, (minute + 5) * 60];

/**
 * The numbered pivot (1-based) whose evidence window holds the moment, or that it set off; 0 when none.
 * `pivots` are in the board's order, each with the window its detail gives.
 */
export function linkedPivot(k: KeyMoment, pivots: readonly { minute: number; trigger_event_ids: string[]; window?: Window | null }[]): number {
  const i = pivots.findIndex((p) => p.trigger_event_ids.includes(k.event.event_id));
  if (i >= 0) return i + 1;
  const j = pivots.findIndex((p) => {
    const [from, to] = pivotWindow(p.minute, p.window);
    return k.event.t >= from && k.event.t <= to;
  });
  return j + 1;
}

/** Where the match stands on the clock, for the label over the board: under way, half-time or full time. */
export function matchPhase(status: string, events: readonly MatchEvent[]): "live" | "halfTime" | "finished" {
  if (status === "finished") return "finished";
  // events are newest first: the last period boundary seen.
  const edge = events.find((e) => e.type === "period_end" || e.type === "kickoff");
  return edge?.type === "period_end" && edge.period === 1 ? "halfTime" : "live";
}
