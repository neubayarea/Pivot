// C18 (#366): the analyst's xG race adds up the API's per-shot xG in time order, and a goal VAR ruled
// out still counts, as it does in the team stats, so each line ends on the team-stats number.
import { describe, expect, it } from "vitest";
import type { ShotMapShot } from "@pivot/contracts";
import { en } from "../i18n/messages/en";
import { es } from "../i18n/messages/es";
import { zh } from "../i18n/messages/zh";
import { KEY_METRICS } from "./KeyMetrics";
import { xgSteps } from "./XgRace";

const shot = (id: string, team: "home" | "away", t: number, xg: number | null, outcome: ShotMapShot["outcome"] = "saved") =>
  ({ event_id: id, team, t, xg, outcome } as ShotMapShot);

describe("xgSteps", () => {
  it("adds each side's xG shot by shot, in time order, marking goals", () => {
    const s = xgSteps([shot("b", "home", 900, 0.3, "goal"), shot("a", "home", 300, 0.1), shot("c", "away", 600, 0.5), shot("d", "home", 1200, null)]);
    expect(s.home.map((x) => [x.id, +x.total.toFixed(2), x.goal])).toEqual([["a", 0.1, false], ["b", 0.4, true], ["d", 0.4, false]]);
    expect(s.away.at(-1)?.total).toBe(0.5);
  });
  it("counts a goal that VAR ruled out, like the team stats do", () => {
    const s = xgSteps([shot("a", "home", 300, 0.2), shot("b", "home", 2900, 0.34, "disallowed")]);
    expect(s.home.at(-1)?.total).toBeCloseTo(0.54);
    expect(s.home.at(-1)?.goal).toBe(false);
  });
});

describe("key metrics", () => {
  it("names and defines every card in en, zh and es", () => {
    for (const m of [en, zh, es] as Record<string, string>[]) {
      for (const [, key] of KEY_METRICS) {
        expect(m[`metric.${key}.short`]).toBeTruthy();
        expect(m[`metric.${key}.def`]).toBeTruthy();
      }
    }
  });
});
