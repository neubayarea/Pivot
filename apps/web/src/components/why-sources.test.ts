// Ax83 (#332, #395): each highlighted figure in a turning point shows its own source.
import { describe, expect, it } from "vitest";
import type { Claim } from "@pivot/contracts";
import { claimsFor } from "./WhyItTurned";
import { plural, translator } from "../i18n";

const claim = (metric: string, value: number, window: [number, number]): Claim =>
  ({ value, unit: "count", stat_ref: { metric, team: "away", window, player_id: null } }) as unknown as Claim;

describe("claimsFor", () => {
  // "Their final-third passes rose from 4 to 14 and box entries from 0 to 5"
  const claims = [
    claim("passes_final_third", 4, [6, 11]), claim("passes_final_third", 14, [11, 16]),
    claim("box_entries", 0, [6, 11]), claim("box_entries", 5, [11, 16]),
  ];

  it("gives each figure the claims with its own numbers", () => {
    const used = new Set<number>();
    const a = claimsFor("4 to 14", claims, used);
    const b = claimsFor("0 to 5", claims, used);
    expect([a?.from?.value, a?.to.value, a?.to.stat_ref.metric]).toEqual([4, 14, "passes_final_third"]);
    expect([b?.from?.value, b?.to.value, b?.to.stat_ref.metric]).toEqual([0, 5, "box_entries"]);
  });

  it("finds a figure's claims out of order, and falls back to the next one when no value matches", () => {
    const used = new Set<number>();
    expect(claimsFor("0 to 5", claims, used)?.to.stat_ref.metric).toBe("box_entries");
    expect(claimsFor("7 to 9", claims, used)?.to.value).toBe(4);
  });
});

describe("plural", () => {
  it("uses the .one form for 1 where a language has it", () => {
    expect(plural(translator("en"), "pre.played", 1)).toBe("1 meeting");
    expect(plural(translator("en"), "pre.played", 3)).toBe("3 meetings");
    expect(plural(translator("es"), "pre.draws", 1)).toBe("1 empate");
  });
});
