// Ax49: following a player shows their card, with the numbers from the #226 endpoint. Rendered to
// static HTML like viewer-settings.test.tsx, so the fetch is tested on the client and the card on a
// report handed to it.
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PlayerReport } from "@pivot/contracts";
import { api } from "../data/live/api";
import { FixtureProvider } from "../data/match";
import { PrefsProvider } from "../i18n";
import PlayerCard, { PlayerCardView } from "./PlayerCard";

const g = globalThis as { window?: { location: { search: string }; localStorage: Pick<Storage, "getItem" | "setItem" | "removeItem"> } };

function withWindow(search: string) {
  const m = new Map<string, string>();
  g.window = { location: { search }, localStorage: { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v), removeItem: (k) => void m.delete(k) } };
}

afterEach(() => {
  delete g.window;
  vi.unstubAllGlobals();
});

const render = (node: ReactNode) =>
  renderToStaticMarkup(
    <PrefsProvider>
      <MemoryRouter>
        <FixtureProvider>{node}</FixtureProvider>
      </MemoryRouter>
    </PrefsProvider>,
  );

const REPORT: PlayerReport = {
  player_id: "hcy-11", name: "A. Moreau", team: "home", shirt_number: 11, role: "ST",
  stats: {
    match_id: "m1", player_id: "hcy-11", up_to_t: 2400, minutes_played: 40, rating: 7.2, goals: 1, assists: 0,
    shots: 3, xg: 0.41, xa: 0.05, passes: 18, pass_accuracy_pct: 83.3, key_passes: 2, progressive_passes: 1,
    dribbles_won: 1, tackles_won: 2, interceptions: 0, duels_won: 4, aerials_won: 1, fouls_committed: 0, saves: 0,
    distance_km: 4.62, top_speed_kmh: 31.4, sprints: 9,
  },
  event_ids: ["e1"],
  pivots: [{ pivot_id: "pv-38", minute: 37, in_trigger: true, event_ids: ["e1"] }],
};

describe("the followed player's card", () => {
  it("asks the players endpoint for that player, up to the clock or for the whole match", async () => {
    const urls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      urls.push(url);
      return Response.json({ match_id: "m1", up_to_t: 2400, source: "computed", players: [REPORT] });
    }));
    expect((await api.playerStats("m1", "hcy-11", 2400)).players[0].name).toBe("A. Moreau");
    await api.playerStats("m1", "hcy-11", null);
    expect(urls).toEqual(["/api/matches/m1/players/stats?player=hcy-11&up_to=2400", "/api/matches/m1/players/stats?player=hcy-11"]);
  });

  it("shows the analyst line, and the moments they were part of", () => {
    withWindow("?player=hcy-11");
    const html = render(<PlayerCardView report={REPORT} upTo={2400} numbered={["pv-38"]} onPivot={() => {}} />);
    expect(html).toContain("Following A. Moreau");
    expect(html).toContain("#11, HCY, ST");
    expect(html).toContain("xG</dt><dd>0.41");
    expect(html).toContain("18 (83%)");
    expect(html).toContain("1: 38′, set it off");
  });

  it("gives a fan plain words and no xG or rating", () => {
    withWindow("?player=hcy-11&mode=fan&lang=zh");
    const html = render(<PlayerCardView report={REPORT} upTo={2400} />);
    expect(html).toContain("关注：A. Moreau");
    expect(html).toContain("跑了（公里）");
    expect(html).not.toContain("预期进球");
    expect(html).not.toContain("评分");
  });

  it("says so when the player has not come on yet", () => {
    withWindow("?player=hcy-11");
    expect(render(<PlayerCardView report={{ ...REPORT, stats: null, pivots: [] }} upTo={600} />)).toContain("Not on the pitch yet.");
  });

  it("stays off with no player followed, and on the fixture, which has no API", () => {
    withWindow("");
    expect(render(<PlayerCard upTo={null} />)).toBe("");
    withWindow("?player=hcy-11&fixture=1");
    expect(render(<PlayerCard upTo={null} />)).toBe("");
  });
});
