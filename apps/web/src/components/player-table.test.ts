// C16 (#366): the analyst's player table keeps one side's players who played, sorted by a column,
// and every column has a short name and a definition in all three languages.
import { describe, expect, it } from "vitest";
import type { PlayerMatchStats, PlayerReport } from "@pivot/contracts";
import { en } from "../i18n/messages/en";
import { es } from "../i18n/messages/es";
import { zh } from "../i18n/messages/zh";
import { PLAYER_COLS, playerRows } from "./PlayerTable";

const row = (id: string, team: "home" | "away", shirt: number, s: Partial<PlayerMatchStats>) =>
  ({ player_id: id, name: id, team, shirt_number: shirt, role: "CM", event_ids: [], pivots: [],
    stats: { minutes_played: 90, rating: 6, xg: 0, pass_accuracy_pct: 80, ...s } as PlayerMatchStats } as PlayerReport);

describe("playerRows", () => {
  const players = [row("h8", "home", 8, { rating: 7.1 }), row("h9", "home", 9, { rating: 8.4, xg: 0.6 }),
    row("h14", "home", 14, { minutes_played: 0 }), row("a9", "away", 9, { rating: 9 }), row("h5", "home", 5, { rating: 7.1, pass_accuracy_pct: null })];

  it("keeps one side's players who played, highest first", () => {
    expect(playerRows(players, "home", "rating", false).map((p) => p.player_id)).toEqual(["h9", "h5", "h8"]);
  });
  it("sorts lowest first when asked, and a missing number goes last when highest first", () => {
    expect(playerRows(players, "home", "rating", true).map((p) => p.player_id)).toEqual(["h5", "h8", "h9"]);
    expect(playerRows(players, "home", "pass_accuracy_pct", false).at(-1)?.player_id).toBe("h5");
  });
});

describe("metric definitions", () => {
  it("has a short name and a definition for every column in en, zh and es", () => {
    for (const m of [en, zh, es] as Record<string, string>[]) {
      for (const c of PLAYER_COLS) {
        expect(m[`metric.${c}.short`]).toBeTruthy();
        expect(m[`metric.${c}.def`]).toBeTruthy();
      }
    }
  });
});
