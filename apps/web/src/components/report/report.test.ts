// C19 (#385): the analyst report's sentences come from the data: the deserved-result verdict, the
// best spell, the most dangerous score state, the 15-minute block of a clock label, and the beeswarm
// keeping dots apart. Every report key exists in all three languages.
import { describe, expect, it } from "vitest";
import { blockOf } from "../../data/analysis";
import { SAMPLE_ANALYSIS } from "../../data/analysis.sample";
import { en } from "../../i18n/messages/en";
import { es } from "../../i18n/messages/es";
import { zh } from "../../i18n/messages/zh";
import { deservedVerdict } from "./Deserved";
import { mostDangerous, stateFor } from "./GameStateTable";
import { bestSpell } from "./Phases";
import { swarm } from "./ShotQuality";

describe("deserved result", () => {
  const d = { n_sims: 10000, home_win: 0.2, draw: 0.3, away_win: 0.5, xpts: { home: 0.9, away: 1.8 } };
  it("says when the chances disagree with the score", () => {
    expect(deservedVerdict(d, { home: 3, away: 3 })).toEqual({ key: "rp.dsv.against", side: "away", p: 0.5 });
  });
  it("says when they agree", () => {
    expect(deservedVerdict(d, { home: 0, away: 1 })).toMatchObject({ key: "rp.dsv.match", side: "away" });
  });
  it("names a draw when a draw was likeliest", () => {
    expect(deservedVerdict({ ...d, draw: 0.6, away_win: 0.2 }, { home: 2, away: 0 })).toMatchObject({ key: "rp.dsv.draw", side: null });
  });
});

describe("match phases", () => {
  it("finds the biggest gap, with PPDA read the other way round", () => {
    expect(bestSpell(SAMPLE_ANALYSIS.phases, "xg")).toEqual({ i: 1, side: "away" });
    const ppda = bestSpell(SAMPLE_ANALYSIS.phases, "ppda")!;
    const p = SAMPLE_ANALYSIS.phases[ppda.i];
    expect(p[ppda.side].ppda!).toBeLessThan(p[ppda.side === "home" ? "away" : "home"].ppda!);
  });
  it("puts stoppage time in the block it belongs to", () => {
    const phases = SAMPLE_ANALYSIS.phases;
    expect(blockOf(phases, "1'")).toBe(0);
    expect(blockOf(phases, "15'")).toBe(0);
    expect(blockOf(phases, "16'")).toBe(1);
    expect(blockOf(phases, "45+2'")).toBe(2);
    expect(blockOf(phases, "90+5")).toBe(5);
  });
});

describe("game state", () => {
  it("names the state, as the side lived it, where it made most xG per 90", () => {
    const md = mostDangerous(SAMPLE_ANALYSIS.game_state)!;
    expect(md.side).toBe("away");
    expect(stateFor(md.row.state, md.side)).toBe("ahead");
    expect(stateFor("home_leading", "away")).toBe("behind");
  });
});

describe("beeswarm", () => {
  it("keeps dots at the same xG apart", () => {
    const ys = swarm([100, 100, 100], 5);
    expect(new Set(ys).size).toBe(3);
  });
});

describe("report text", () => {
  it("has every report key in en, zh and es", () => {
    const keys = Object.keys(en).filter((k) => k.startsWith("rp.") || ["metric.xpts", "metric.xg_per90", "metric.xga_per90", "metric.xg_per_shot", "metric.big_chances"].some((m) => k.startsWith(m)));
    expect(keys.length).toBeGreaterThan(40);
    for (const m of [zh, es] as Record<string, string>[]) for (const k of keys) expect(m[k], k).toBeTruthy();
  });
});
