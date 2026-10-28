// C21 (P0): a score state under 15 minutes shows its xG as it stands, with a note, not a per-90 rate
// (four minutes level read 20.86 xG/90), and the takeaway sentence only uses states of 15 minutes or more.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { GameState } from "../../data/analysis";
import { PrefsProvider } from "../../i18n";
import GameStateTable, { isShort, mostDangerous } from "./GameStateTable";

const line = (xg: number, xga: number) => ({ xg_per90: xg, xga_per90: xga, possession_pct: 50, field_tilt_pct: 50 });
const ROWS: GameState[] = [
  { state: "level", minutes: 4, home: line(20.86, 2.05), away: line(2.05, 20.86) },
  { state: "home_leading", minutes: 75.8, home: line(1.72, 0.52), away: line(0.52, 1.72) },
];

describe("short score states", () => {
  it("are under 15 minutes", () => {
    expect(ROWS.map(isShort)).toEqual([true, false]);
  });
  it("are left out of the takeaway", () => {
    expect(mostDangerous(ROWS)).toMatchObject({ side: "home", row: { state: "home_leading" } });
  });
  it("show xG as it stands with a note, not 20.86 per 90", () => {
    const html = renderToStaticMarkup(<PrefsProvider><GameStateTable rows={ROWS} names={{ home: "BRI", away: "FAL" }} /></PrefsProvider>);
    expect(html).not.toContain("20.86");
    expect(html).toContain("0.93");
    expect(html).toContain("rp-short-note");
  });
});
