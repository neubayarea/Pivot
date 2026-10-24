import { describe, expect, it } from "vitest";
import type { Match, MatchEvent, MinuteMetric, Pivot1 as Pivot } from "@pivot/contracts";
import { replayEnd, replayStart, stateAt } from "./replay";
import type { LiveState } from "./state";

const match = {
  match_id: "m1", clock: 5700, period: 2, status: "finished", speed: 1,
  score: { home: 1, away: 1, home_penalties: null, away_penalties: null },
  periods: [{ period: 1, start_t: 0, end_t: 2760 }, { period: 2, start_t: 2760, end_t: 5700 }],
} as unknown as Match;
const ev = (seq: number, t: number, extra: Partial<MatchEvent> = {}) =>
  ({ event_id: `e${seq}`, seq, t, team: "home", type: "pass", ...extra }) as MatchEvent;
const full: LiveState = {
  match,
  events: [ev(1, 0), ev(2, 600, { type: "shot", shot_outcome: "goal" }), ev(3, 3000, { team: "away", type: "shot", shot_outcome: "goal" })],
  metrics: [0, 10, 50].map((minute) => ({ match_id: "m1", minute, momentum: 0 }) as MinuteMetric),
  pivots: [
    { pivot_id: "m1:p10", match_id: "m1", minute: 10, status: "confirmed", narrative: {} } as Pivot,
    { pivot_id: "m1:p20", match_id: "m1", minute: 20, status: "rejected" } as Pivot,
  ],
};

describe("replay of a stored match", () => {
  it("reads the start minute from ?from=", () => {
    expect(replayStart("?match=m1&from=0")).toBe(0);
    expect(replayStart("?from=74")).toBe(74 * 60);
    expect(replayStart("?match=m1")).toBeNull();
    expect(replayStart("?from=x")).toBeNull();
  });

  it("shows only what happened by the clock, with the score so far", () => {
    const s = stateAt(full, 599, true);
    expect(s.events.map((e) => e.seq)).toEqual([1]);
    expect(s.metrics.map((m) => m.minute)).toEqual([0]);
    expect(s.match).toMatchObject({ clock: 599, status: "live", period: 1, score: { home: 0, away: 0 } });
    expect(stateAt(full, 3000, false).match).toMatchObject({ status: "paused", period: 2, score: { home: 1, away: 1 } });
  });

  it("brings pivots in as pending after their minute, then settled; never rejected ones", () => {
    expect(stateAt(full, 10 * 60 + 59, true).pivots).toEqual([]);
    expect(stateAt(full, 11 * 60, true).pivots.map((p) => [p.pivot_id, p.status, p.narrative])).toEqual([["m1:p10", "pending", null]]);
    expect(stateAt(full, 11 * 60 + 40, true).pivots.map((p) => p.status)).toEqual(["confirmed"]);
    expect(stateAt(full, 5700, true).pivots.map((p) => p.pivot_id)).toEqual(["m1:p10"]);
  });

  it("ends on the final clock with the stored result", () => {
    expect(replayEnd(full)).toBe(5700);
    expect(stateAt(full, 5700, true).match).toMatchObject({ status: "finished", score: match.score });
  });
});
