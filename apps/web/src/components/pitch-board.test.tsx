// Ax36: who is who on the pitch board, and the team-shape numbers. Static HTML, no DOM.
import type React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import type { MatchEvent, TeamSheet, TrackingFrame } from "@pivot/contracts";
import { FixtureProvider } from "../data/match";
import { PrefsProvider } from "../i18n";
import Pitch from "./Pitch";
import { PlayerDetail, Roster, ShapeTable } from "./PitchBoard";
import { frameShape, lineupAt, meanShape, shapeLines } from "./shape";

const slot = (player_id: string, role: TeamSheet["starters"][number]["role"]) => ({ player_id, role, slot: 0, anchor: [0, 0] });
const sheet = (formation: string, starters: ReturnType<typeof slot>[]) => ({ formation, starters, bench: [] }) as unknown as TeamSheet;
const sheets = {
  home: sheet("4-3-3", [slot("h1", "GK"), slot("h2", "CB"), slot("h3", "CB"), slot("h9", "ST")]),
  away: sheet("4-4-2", [slot("a1", "GK"), slot("a2", "CB"), slot("a3", "CB"), slot("a9", "ST")]),
};
const at = (id: string, x: number, y: number) => ({ player_id: id, x, y, fitness: 1, speed_ms: 0 });
const frame = (t: number, shift = 0): TrackingFrame => ({
  match_id: "m", t, period: 1, possession: "home",
  ball: { x: 50, y: 34, z: 0, owner_id: "h9" },
  players: [at("h1", 5, 34), at("h2", 30 + shift, 20), at("h3", 30 + shift, 48), at("h9", 60, 34),
    at("a1", 100, 34), at("a2", 70, 24), at("a3", 70, 44), at("a9", 45, 34)],
});
const isHome = (id: string) => id.startsWith("h");
const ev = (o: Partial<MatchEvent>) => ({ t: 0, team: "home", meta: {}, substitution: null, team_sheet: null, ...o }) as MatchEvent;

describe("team shape", () => {
  const { roles, formation } = lineupAt(sheets, [], 100);

  it("measures back line from each team's own goal, width and depth over outfield players", () => {
    expect(frameShape(frame(1), "home", roles, isHome)).toEqual({ backLine: 30, width: 28, depth: 30 });
    // Away defends the right-hand goal: 105 - 70.
    expect(frameShape(frame(1), "away", roles, isHome)).toEqual({ backLine: 35, width: 20, depth: 25 });
    expect(formation).toEqual({ home: "4-3-3", away: "4-4-2" });
  });

  it("averages the earlier frames for the comparison", () => {
    expect(meanShape([frame(1, 0), frame(2, -10)], "home", roles, isHome)?.backLine).toBe(25);
  });

  it("joins the defenders across the pitch and leaves a line of one undrawn", () => {
    expect(shapeLines(frame(1), "home", roles, isHome)).toEqual([[[30, 20], [30, 48]]]);
  });

  it("takes the latest team sheet at the clock", () => {
    const change = ev({ t: 50, team: "home", team_sheet: sheet("5-4-1", [slot("h2", "LWB")]) });
    expect(lineupAt(sheets, [change], 49).formation.home).toBe("4-3-3");
    expect(lineupAt(sheets, [change], 50).roles.get("h2")).toBe("LWB");
  });

  it("shows the numbers with the earlier average next to them", () => {
    const html = renderToStaticMarkup(<ShapeTable frame={frame(1)} lineup={lineupAt(sheets, [], 1)} before={[frame(0, -10)]}
      beforeLabel="x" isHome={isHome} names={{ home: "HOM", away: "AWY" }} />);
    expect(html).toContain("4-3-3");
    expect(html).toContain("← 20 (+10)");
  });
});

describe("who is who", () => {
  const tag = (id: string) => ({ h9: "9 · Striker · ST" })[id] ?? id;

  it("labels the picked player and rings the ball carrier and the action's players", () => {
    const html = renderToStaticMarkup(<Pitch frame={frame(1)} actions={[]} selected={null} label="pitch" picked="h2"
      onPick={() => {}} marked={new Set(["a9"])} tag={tag} />);
    expect(html).toContain("<title>9 · Striker · ST</title>");
    expect(html).toContain('class="pl picked pick"');
    expect(html).toContain('class="pl marked pick"');
    expect(html).toContain('class="pl carrier pick"');
    expect(html).toContain('class="pl-label"');
  });

  it("greys out players who went off or were sent off, and marks who came on", () => {
    const squads = {
      home: [{ player_id: "h2", name: "Back", shirt: 2 }, { player_id: "h9", name: "Striker", shirt: 9 },
        { player_id: "h14", name: "Sub", shirt: 14 }, { player_id: "h20", name: "Unused", shirt: 20 }],
      away: [{ player_id: "a3", name: "Red", shirt: 3 }],
    };
    const events = [
      ev({ t: 60, type: "card", team: "away", player_id: "a3", foul: { card: "red" } as MatchEvent["foul"] }),
      ev({ t: 50, type: "substitution", substitution: { player_on_id: "h14", player_off_id: "h2" } as MatchEvent["substitution"] }),
    ];
    const f = { ...frame(70), players: [at("h9", 60, 34), at("h14", 30, 30)] };
    const html = renderToStaticMarkup(<Roster squads={squads} frame={f} now={70} events={events} roleOf={() => undefined}
      picked={null} marked={new Set()} onPick={() => {}} names={{ home: "HOM", away: "AWY" }} />);
    expect(html).toMatch(/disabled="" aria-pressed="false" class="off".*Back/);
    expect(html).toMatch(/class="cameOn".*Sub.*on</);
    expect(html).toMatch(/class="sentOff".*Red.*sent off/);
    expect(html).not.toContain("Unused");
  });
});

describe("a player in the line-ups card (Ax59)", () => {
  const g = globalThis as { window?: unknown };
  afterEach(() => void delete g.window);
  const view = (node: React.ReactNode) => {
    g.window = { location: { search: "?fixture=1" }, localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} } };
    return renderToStaticMarkup(<PrefsProvider><MemoryRouter><FixtureProvider>{node}</FixtureProvider></MemoryRouter></PrefsProvider>);
  };
  const okafor = { player_id: "hcy-9", name: "D. Okafor", shirt: 9 };

  it("shows who it is, their side and role, and a Back button to the list", () => {
    const html = view(<PlayerDetail player={okafor} role="ST" onBack={() => {}} />);
    expect(html).toContain("← Back");
    expect(html).toContain("D. Okafor");
    expect(html).toContain("Harbour City · ST");
    expect(html).toContain('class="roster-detail home"');
    // The fixture has no player numbers to fetch: it says so instead of an empty box.
    expect(html).toContain("No numbers for this player in this match yet.");
  });

  it("tells the viewer a name or a dot opens the player", () => {
    expect(view(<Roster squads={{ home: [okafor], away: [] }} frame={null} now={0} events={[]} roleOf={() => "ST"}
      picked={null} marked={new Set()} onPick={() => {}} names={{ home: "HCY", away: "NVR" }} />))
      .toContain("Tap a name or a dot on the pitch for the player&#x27;s numbers.");
  });
});
