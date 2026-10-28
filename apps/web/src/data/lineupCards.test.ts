// C21 (#401): the line-ups tab picks a player's three stats by role, counts the ratings in bands, and
// reads each substitution from the side that made it.
import { describe, expect, it } from "vitest";
import type { AnalysisSub, PlayerMatchStats, PlayerReport } from "@pivot/contracts";
import { en } from "../i18n/messages/en";
import { es } from "../i18n/messages/es";
import { zh } from "../i18n/messages/zh";
import { BANDS, CARD_STATS, cardStats, cardValue, ratingSpread, roleGroup, subImpact } from "./lineupCards";

const stats = (over: Partial<PlayerMatchStats>): PlayerMatchStats =>
  ({ minutes_played: 90, rating: 7.1, saves: 4, passes: 30, pass_accuracy_pct: 81.4, tackles_won: 3, interceptions: 2,
    progressive_passes: 5, key_passes: 1, xg: 0.43, shots: 3, ...over }) as PlayerMatchStats;
const player = (team: "home" | "away", role: string, over: Partial<PlayerMatchStats> | null = {}): PlayerReport =>
  ({ player_id: `${team}-${role}`, name: role, team, role, shirt_number: 1, stats: over && stats(over) }) as unknown as PlayerReport;

describe("a player's card", () => {
  it("shows the three stats for his role", () => {
    expect(roleGroup("GK")).toBe("gk");
    expect(roleGroup("RWB")).toBe("def");
    expect(roleGroup("AM")).toBe("mid");
    expect(roleGroup("ST")).toBe("fwd");
    expect(cardStats(player("home", "GK")).map((s) => s.key)).toEqual(["saves", "pass_accuracy_pct", "passes"]);
    expect(cardStats(player("home", "ST"))).toEqual([{ key: "xg", value: 0.43 }, { key: "shots", value: 3 }, { key: "key_passes", value: 1 }]);
    expect(cardStats(player("home", "CB", null)).every((s) => s.value === null)).toBe(true);
  });
  it("writes each kind of number its own way", () => {
    expect(cardValue("xg", 0.4321)).toBe("0.43");
    expect(cardValue("pass_accuracy_pct", 81.4)).toBe("81%");
    expect(cardValue("tackles_won", 3)).toBe("3");
    expect(cardValue("shots", null)).toBe("–");
  });
  it("has a label for every stat in every language", () => {
    for (const key of new Set(Object.values(CARD_STATS).flat())) {
      for (const table of [en, zh, es] as Record<string, string | undefined>[]) expect(table[`lu.stat.${key}`]).toBeTruthy();
    }
  });
});

describe("the squad's ratings in bands", () => {
  it("counts players with at least 20 minutes, per side", () => {
    const spread = ratingSpread([
      player("home", "CB", { rating: 5.8 }), player("home", "ST", { rating: 8.2 }), player("home", "CM", { rating: 7.0 }),
      player("away", "GK", { rating: 6.5 }), player("away", "LW", { rating: 9.9, minutes_played: 12 }), player("away", "RB", null),
    ]);
    expect(spread.home).toEqual([1, 0, 0, 1, 0, 1]);
    expect(spread.away).toEqual([0, 0, 1, 0, 0, 0]);
    expect(BANDS).toHaveLength(6);
  });
});

describe("what a substitution changed", () => {
  const sub = {
    event_id: "e1", t: 3480, minute: 58, clock: 54, period: 2, team: "away", player_off_id: "a9", player_off_name: "A",
    player_on_id: "a15", player_on_name: "B", reason: "tactical", window_before: [50, 58], window_after: [58, 73],
    minutes_before: 8, minutes_after: 15, cut_before: "half_time", cut_after: null,
    before: { home: { xg: 0.14, field_tilt_pct: 84.2 }, away: { xg: 0.0, field_tilt_pct: 15.8 } },
    after: { home: { xg: 0.05, field_tilt_pct: 60.1 }, away: { xg: 0.31, field_tilt_pct: 39.9 } },
  } as unknown as AnalysisSub;
  it("is read from the side that made it", () => {
    const row = subImpact(sub);
    expect(row.xg).toEqual([0.0, 0.31]);
    expect(row.xga).toEqual([0.14, 0.05]);
    expect(row.tilt).toEqual([15.8, 39.9]);
    expect(row.tiltChange).toBe(24.1);
  });
  it("has no change where a window has no field tilt", () => {
    const none = { ...sub, after: { ...sub.after, away: { xg: 0, field_tilt_pct: null } } } as unknown as AnalysisSub;
    expect(subImpact(none).tiltChange).toBeNull();
  });
});
