// C21 (#401): the analyst's pitch overlays use the stats' own event filters. Progressive passes follow
// the StatCalculator's ATTR-011 rule; lanes are completed passes (no throw-ins) zone to zone in the last
// three minutes; pressing is pressures, tackles and interceptions in the last five.
import { describe, expect, it } from "vitest";
import type { MatchEvent } from "@pivot/contracts";
import { completedPass, passLanes, pressEvents, progressive } from "./PitchOverlays";

const pass = (over: Partial<MatchEvent>) => ({ event_id: "e", type: "pass", team: "home", outcome: "success", pass_type: "regular", t: 100, location: [30, 34], end_location: [40, 34], ...over } as MatchEvent);

describe("progressive passes (ATTR-011)", () => {
  it("needs 30 m inside the own half, 15 m into the other half, 10 m inside it", () => {
    expect(progressive(pass({ location: [5, 34], end_location: [36, 34] }))).toBe(true);
    expect(progressive(pass({ location: [5, 34], end_location: [30, 34] }))).toBe(false);
    expect(progressive(pass({ location: [45, 34], end_location: [61, 34] }))).toBe(true);
    expect(progressive(pass({ location: [70, 34], end_location: [81, 34] }))).toBe(true);
    expect(progressive(pass({ location: [70, 34], end_location: [78, 34] }))).toBe(false);
  });
  it("reads the away side attacking to the left, and never counts corners, throw-ins or misses", () => {
    expect(progressive(pass({ team: "away", location: [35, 34], end_location: [24, 34] }))).toBe(true);
    expect(progressive(pass({ pass_type: "corner", location: [70, 34], end_location: [100, 34] }))).toBe(false);
    expect(progressive(pass({ outcome: "fail", location: [70, 34], end_location: [100, 34] }))).toBe(false);
  });
});

describe("passing lanes", () => {
  it("groups completed passes zone to zone in the last three minutes", () => {
    const evs = [pass({ t: 290 }), pass({ t: 295, event_id: "b" }), pass({ t: 50, event_id: "old" }), pass({ t: 296, event_id: "ti", pass_type: "throw_in" })];
    expect(completedPass(evs[3])).toBe(false);
    const lanes = passLanes(evs, 300);
    expect(lanes).toHaveLength(1);
    expect(lanes[0].n).toBe(2);
  });
});

describe("pressing zones", () => {
  it("takes pressures, tackles and interceptions with a place, in the last five minutes", () => {
    const evs = ["pressure", "tackle", "interception", "pass"].map((type, i) => ({ event_id: String(i), type, team: "home", t: 500, location: [50, 30] } as MatchEvent));
    expect(pressEvents([...evs, { ...evs[0], event_id: "x", t: 100 }], 600).map((e) => e.type)).toEqual(["pressure", "tackle", "interception"]);
  });
});
