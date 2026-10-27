// C19 B (#385): attacking lanes as shares of the entries, the radar's geometry, and the top
// contributors by xG + xA among the players who played.
import { describe, expect, it } from "vitest";
import type { PlayerMatchStats, PlayerReport } from "@pivot/contracts";
import { SAMPLE_ANALYSIS } from "../../data/analysis.sample";
import { laneShares } from "./Lanes";
import { topContributors } from "./PlayerContrib";
import { radarPoint } from "./StyleRadar";

describe("attacking lanes", () => {
  it("gives each lane its share of the entries", () => {
    const s = laneShares(SAMPLE_ANALYSIS.lanes.home);
    expect(s).toEqual({ left: 41, centre: 26, right: 32 });
  });
});

describe("style radar", () => {
  it("puts the first axis straight up and 0 at the centre", () => {
    const [x, y] = radarPoint(0, 8, 100);
    expect(Math.round(x)).toBe(170);
    expect(y).toBeLessThan(170);
    expect(radarPoint(3, 8, 0)).toEqual([170, 170]);
  });
});

describe("key players", () => {
  const p = (id: string, xg: number, xa: number, minutes = 90) =>
    ({ player_id: id, name: id, team: "home", shirt_number: 1, stats: { xg, xa, minutes_played: minutes } as PlayerMatchStats } as PlayerReport);
  it("ranks by xG + xA, leaving out players with none or who did not play", () => {
    const top = topContributors([p("a", 0.2, 0.1), p("b", 0.5, 0.4), p("c", 0, 0), p("d", 0.9, 0, 0)], 8);
    expect(top.map((x) => x.player_id)).toEqual(["b", "a"]);
  });
});
