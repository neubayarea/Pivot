// C12 (#311): the persona helpers every tab shares.
import { describe, expect, it } from "vitest";
import type { PlayerReport, StatMetricInfo, TeamStatsReport } from "@pivot/contracts";
import { en } from "../i18n/messages/en";
import { zh } from "../i18n/messages/zh";
import { bestPlayer, coreStats, forYourTeam, lean, listOf, result, strengthsAndWeaknesses, swingAt, teamLine, teamRating } from "./persona";

const metric = (m: string, unit: StatMetricInfo["unit"] = "count"): StatMetricInfo => ({
  metric: m, definition_id: "MET-000", unit, decimals: 0, group: "attack", label: m, fan_label: m, description: "", higher_means: "",
} as StatMetricInfo);

const report = (home: Record<string, number | null>, away: Record<string, number | null>): TeamStatsReport => ({
  match_id: "M", up_to_t: 5400,
  metrics: Object.keys(home).map((m) => metric(m)),
  scopes: [{ scope: "match", period: null, window: [0, 90], home, away }],
});

const player = (id: string, team: "home" | "away", rating: number, minutes = 90): PlayerReport => ({
  player_id: id, name: id, team, role: "CM", shirt_number: 8, event_ids: [], pivots: [],
  stats: { rating, minutes_played: minutes } as PlayerReport["stats"],
});

const tr = (dict: Record<string, string>) => (key: string, vars: Record<string, string | number> = {}) =>
  (dict[key] ?? key).replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));

describe("for you / against you", () => {
  it("follows the pivot's direction, and says nothing with no team picked", () => {
    expect(lean({ direction: "home" }, "home")).toBe("for");
    expect(lean({ direction: "home" }, "away")).toBe("against");
    expect(lean({ direction: "away" }, null)).toBeNull();
  });
  it("reads the result from the picked side", () => {
    expect(result({ home: 2, away: 1 }, "home")).toBe("win");
    expect(result({ home: 2, away: 1 }, "away")).toBe("loss");
    expect(result({ home: 3, away: 3 }, "away")).toBe("draw");
  });
});

describe("your team's strongest and weakest stats", () => {
  const r = report(
    { shots: 14, box_entries: 20, possession_pct: 50, ppda: 6, turnovers: 40, line_height_m: 45, duels_won: 30, xg: null },
    { shots: 7, box_entries: 19, possession_pct: 50, ppda: 12, turnovers: 60, line_height_m: 30, duels_won: 45, xg: 1.2 },
  );
  const { strengths, weaknesses } = strengthsAndWeaknesses(r, "home");

  it("ranks by the relative gap, PPDA and turnovers counting the other way round", () => {
    expect(strengths.map((e) => e.metric)).toEqual(["shots", "ppda", "turnovers"]);
    expect(weaknesses.map((e) => e.metric)).toEqual(["duels_won"]);
  });
  it("leaves out level stats, shape stats with no better side, and missing values", () => {
    const all = [...strengths, ...weaknesses].map((e) => e.metric);
    for (const m of ["possession_pct", "line_height_m", "xg"]) expect(all).not.toContain(m);
  });
  it("is the mirror image for the other team", () => {
    const away = strengthsAndWeaknesses(r, "away");
    expect(away.strengths.map((e) => e.metric)).toEqual(["duels_won"]);
    expect(away.weaknesses[0].metric).toBe("shots");
  });
  it("has nothing to say without a report", () => {
    expect(strengthsAndWeaknesses(null, "home")).toEqual({ strengths: [], weaknesses: [] });
  });
});

describe("players", () => {
  const ps = [player("a", "home", 7.9), player("b", "home", 8.4, 12), player("c", "away", 8.1), player("d", "home", 6.5)];
  it("best player: highest rating among those who played 20 minutes or more", () => {
    expect(bestPlayer(ps)?.player_id).toBe("c");
    expect(bestPlayer(ps, "home")?.player_id).toBe("a");
    expect(bestPlayer([])).toBeNull();
  });
  it("team rating averages the same players", () => {
    expect(teamRating(ps, "home")).toBeCloseTo(7.2);
    expect(teamRating(ps, "away")).toBeCloseTo(8.1);
  });
  it("six core numbers by position", () => {
    expect(coreStats("GK")).toContain("saves");
    expect(coreStats("CB")).toContain("aerials_won");
    expect(coreStats("CM")).toContain("key_passes");
    expect(coreStats("ST")).toEqual(["goals", "shots", "xg", "key_passes", "dribbles_won", "sprints"]);
    for (const r of ["GK", "LB", "DM", "RW"]) expect(coreStats(r)).toHaveLength(6);
  });
});

describe("the one-sentence summary", () => {
  const o = { team: "Harbour City", score: { home: 3, away: 3 }, side: "home" as const,
    strengths: ["Shots", "Box entries"], weaknesses: ["Duels won"], best: { name: "A. Moreau", rating: 7.84 } };
  it("reads as plain sentences in English, with no · chains", () => {
    const s = teamLine(tr(en), "en", o);
    expect(s).toBe("Harbour City drew 3–3. Ahead on shots and box entries. Behind on duels won. Best player: A. Moreau, rated 7.8.");
    expect(s).not.toContain("·");
  });
  it("in Chinese keeps the labels as they are and joins without spaces", () => {
    const s = teamLine(tr(zh), "zh", { ...o, strengths: ["射门", "进入禁区"], weaknesses: [] });
    expect(s.startsWith("Harbour City 3–3 战平。占上风的是射门和进入禁区。")).toBe(true);
  });
  it("says level when nothing stands out", () => {
    expect(teamLine(tr(en), "en", { ...o, strengths: [], weaknesses: [], best: null })).toBe("Harbour City drew 3–3. Level on everything that counts.");
  });
  it("lists in each language", () => {
    expect(listOf(["Shots", "Passes", "Xg"], "en")).toBe("shots, passes, and xg");
    expect(listOf(["射门", "传球"], "zh")).toBe("射门和传球");
  });
});

describe("fans' summary", () => {
  it("can keep to the plain stats only", () => {
    const r = report({ shots: 14, ppda: 6, duels_won: 30 }, { shots: 7, ppda: 12, duels_won: 45 });
    const { strengths, weaknesses } = strengthsAndWeaknesses(r, "home", 3, new Set(["shots", "duels_won"]));
    expect(strengths.map((e) => e.metric)).toEqual(["shots"]);
    expect(weaknesses.map((e) => e.metric)).toEqual(["duels_won"]);
  });
});

describe("what-if choices for your team", () => {
  const opts = [
    { type: "cancel_substitution", team: "home" as const },
    { type: "remove_goal", team: "away" as const },
    { type: "change_press", team: "away" as const },
    { type: "remove_red_card", team: "home" as const },
  ];
  it("puts what would have helped your team first, then your own decisions", () => {
    expect(forYourTeam(opts, "home").map((o) => o.type)).toEqual(["remove_goal", "remove_red_card", "cancel_substitution", "change_press"]);
    expect(forYourTeam(opts, "away").map((o) => o.type)).toEqual(["change_press", "cancel_substitution", "remove_goal", "remove_red_card"]);
  });
  it("keeps the order with no team picked", () => {
    expect(forYourTeam(opts, null)).toEqual(opts);
  });
});

describe("the alarm's swing", () => {
  const metrics = Array.from({ length: 20 }, (_, m) => ({ minute: m, momentum: m < 10 ? -0.2 : 0.3 }));
  it("is after minus before, signed towards the side it turned to", () => {
    const s = swingAt(metrics, 10, "home");
    expect(s.before).toBeCloseTo(-0.2);
    expect(s.after).toBeCloseTo(0.3);
    expect(s.swing).toBeCloseTo(0.5);
    expect(swingAt(metrics, 10, "away").swing).toBeCloseTo(-0.5);
  });
  it("is unknown without minutes on both sides", () => {
    expect(swingAt(metrics, 0, "home").swing).toBeNull();
  });
});
