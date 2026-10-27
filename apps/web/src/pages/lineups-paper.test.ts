// C18 (#366): the formation on paper for "paper vs actual": the keeper, then one row per number,
// back to front, each row from the team's left (the far touchline when it attacks to the right).
import { describe, expect, it } from "vitest";
import { paperSlots } from "./match/LineupsTab";

const sheet = (formation: string, n: number) => ({ formation, starters: Array.from({ length: n }, (_, i) => ({ player_id: `p${i + 1}`, slot: i + 1 })) });

describe("paperSlots", () => {
  it("places a 4-3-3 from the keeper forward, left to right", () => {
    const s = paperSlots(sheet("4-3-3", 11));
    expect(s.size).toBe(11);
    expect(s.get("p1")).toEqual([5, 34]);
    // The left-back is nearer the far touchline than the right-back; the forwards are furthest up.
    expect(s.get("p2")![1]).toBeGreaterThan(s.get("p5")![1]);
    expect(s.get("p9")![0]).toBeGreaterThan(s.get("p6")![0]);
  });
  it("gives nothing when the sheet does not add up to its formation", () => {
    expect(paperSlots(sheet("4-4-2", 10)).size).toBe(0);
    expect(paperSlots(sheet("odd", 11)).size).toBe(0);
  });
});
