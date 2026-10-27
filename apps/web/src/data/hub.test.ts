import { describe, expect, it } from "vitest";
import { isHubPage } from "../pages/Hub";
import { byMatchday, liveNow, pinned, type HubLine, type HubLive } from "./hub";
import { TABS, tabFrom, tabOpen } from "./tab";
import { LIVE_ANCHOR, LIVE_BREAK_S, boardHref, liveClock } from "./liveClock";

const at = (s: number) => (LIVE_ANCHOR + s) * 1000;

describe("the simulated live clock (C14)", () => {
  it("is the same second for everyone and starts again after full time and a break", () => {
    const length = 95 * 60;
    expect(liveClock(length, at(0))).toBe(0);
    expect(liveClock(length, at(600.4))).toBe(600);
    expect(liveClock(length, at(length + LIVE_BREAK_S + 61))).toBe(61);
    expect(liveClock(length, at(-1))).toBe(length + LIVE_BREAK_S - 1);
  });

  it("shows only the goals and turning points the clock has reached", () => {
    const live: HubLive = {
      match_id: "M-seed-212", length_s: 95 * 60, periods: [{ period: 1, start_t: 0 }, { period: 2, start_t: 47 * 60 }],
      goals: [{ t: 600, team: "home" }, { t: 3000, team: "away" }], pivot_minutes: [9, 49],
    };
    expect(liveNow(live, at(599))).toMatchObject({ score: { home: 0, away: 0 }, minute: "10", lastPivot: null, over: false });
    expect(liveNow(live, at(601))).toMatchObject({ score: { home: 1, away: 0 }, lastPivot: 9 });
    expect(liveNow(live, at(2999))).toMatchObject({ score: { home: 1, away: 0 }, minute: "48", lastPivot: 9 });
    expect(liveNow(live, at(3001))).toMatchObject({ score: { home: 1, away: 1 }, lastPivot: 49 });
    expect(liveNow(live, at(95 * 60 + 5))).toMatchObject({ score: { home: 1, away: 1 }, lastPivot: 49, over: true });
  });
});

describe("the match centre's links", () => {
  it("is the home page with no match in the link", () => {
    expect(isHubPage("/", "")).toBe(true);
    expect(isHubPage("/", "?tab=overview")).toBe(true);
    expect(isHubPage("/", "?match=M-seed-101")).toBe(false);
    expect(isHubPage("/trace", "")).toBe(false);
  });

  it("sends the back links to the match, keeping a link that names it", () => {
    expect(boardHref("M-seed-101", "")).toBe("/?match=M-seed-101");
    expect(boardHref("M-seed-212", "?match=M-seed-212&live=1")).toBe("/?match=M-seed-212&live=1");
  });

  it("groups results by matchday, latest first, the ones without a matchday last", () => {
    const line = (match_id: string, matchday: number | null) => ({ match_id, matchday }) as HubLine;
    const groups = byMatchday([line("a", 12), line("b", null), line("c", 20), line("d", 12)]);
    expect(groups.map(([day, ls]) => [day, ls.map((l) => l.match_id)])).toEqual([[20, ["c"]], [12, ["a", "d"]], [null, ["b"]]]);
  });
});

describe("the next round (C14 PR 2)", () => {
  it("opens a match before kick-off on its preview, and only the preview and line-ups", () => {
    expect(tabFrom("", "scheduled")).toBe("preview");
    expect(tabFrom("?tab=overview", "scheduled")).toBe("preview");
    expect(tabFrom("?tab=lineups", "scheduled")).toBe("lineups");
    expect(tabFrom("?tab=overview", "finished")).toBe("overview");
    expect(TABS.filter((tab) => tabOpen(tab, "scheduled"))).toEqual(["lineups", "preview"]);
  });

  it("puts the viewer's club's games first", () => {
    const team = (short_name: string) => ({ name: short_name, short_name, color: "#000000" });
    const games = [["LUN", "ELM"], ["ROV", "GRE"], ["THO", "HBC"]].map(([h, a]) => ({ home: team(h), away: team(a) }));
    expect(pinned(games, "HBC").map((g) => g.home.short_name)).toEqual(["THO", "LUN", "ROV"]);
    expect(pinned(games, null)).toBe(games);
  });
});
