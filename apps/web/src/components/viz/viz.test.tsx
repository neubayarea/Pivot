// Bx12: the match pictures, rendered to static HTML like player-card.test.tsx. Points come in each
// team's attacking view (CONV-002); the away side is flipped only where both teams share a pitch.
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import type { AveragePositionsReport, HeatmapReport, PassNetworkReport, ShotMap as ShotMapData } from "@pivot/contracts";
import { vizPath, vizQuery } from "../../data/viz";
import { PrefsProvider } from "../../i18n";
import { AveragePositions, Heatmap, PassNetwork, ShotMap, VizBox, heatCells, shotRadius } from ".";
import { hubsOf, pairsOf } from "./PassNetwork";
import { W, toPx } from "./pitch";

const g = globalThis as { window?: { location: { search: string }; localStorage: Pick<Storage, "getItem" | "setItem" | "removeItem"> } };

// English unless asked: without ?lang= the page would follow the machine's language.
function render(node: ReactNode, search = "?lang=en") {
  const m = new Map<string, string>();
  g.window = { location: { search }, localStorage: { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v), removeItem: (k) => void m.delete(k) } };
  return renderToStaticMarkup(<PrefsProvider>{node}</PrefsProvider>);
}

afterEach(() => {
  delete g.window;
});

const SQUADS = {
  home: [{ player_id: "h09", name: "A. Moreau", shirt: 9 }, { player_id: "h05", name: "B. Lind", shirt: 5 },
         { player_id: "h01", name: "C. Okoro", shirt: 1 }],
  away: [{ player_id: "a10", name: "D. Silva", shirt: 10 }],
};

const SHOTS: ShotMapData = {
  match_id: "m1", up_to_t: 5400, period: null, shots: [
    { event_id: "e1", t: 600, period: 1, clock_label: "10'", team: "home", player_id: "h09", x: 95, y: 30, end_x: 105, end_y: 33,
      xg: 0.3, outcome: "goal", body_part: "right_foot", play_pattern: "open_play", technique: "normal", under_pressure: false, first_time: false },
    { event_id: "e2", t: 1200, period: 1, clock_label: "20'", team: "away", player_id: "a10", x: 90, y: 40, end_x: 105, end_y: 36,
      xg: 0.05, outcome: "saved", body_part: "head", play_pattern: "corner", technique: "normal", under_pressure: true, first_time: false },
    { event_id: "e3", t: 3000, period: 2, clock_label: "50'", team: "home", player_id: "h05", x: 80, y: 34, end_x: null, end_y: null,
      xg: 0.02, outcome: "blocked", body_part: "left_foot", play_pattern: "open_play", technique: "normal", under_pressure: false, first_time: true },
  ],
};

describe("shot map", () => {
  it("draws every shot, home attacking right and away flipped to the left", () => {
    const html = render(<ShotMap data={SHOTS} squads={SQUADS} />);
    expect(html.match(/class="viz-shot/g)).toHaveLength(3);
    const [hx] = toPx(95, 30);
    const [ax] = toPx(90, 40, true);
    expect(hx).toBeGreaterThan(W / 2);
    expect(ax).toBeLessThan(W / 2);
    expect(html).toContain(`cx="${ax}"`);
  });

  it("analyst: size and tooltip carry xG; fan: no xG anywhere, a legend in words", () => {
    const analyst = render(<ShotMap data={SHOTS} squads={SQUADS} />);
    expect(analyst).toContain("10′, A. Moreau: Goal, xG 0.30");
    expect(analyst).toContain("Home: 2 shots, 1 scored, xG 0.32");
    const fan = render(<ShotMap data={SHOTS} squads={SQUADS} />, "?lang=en&mode=fan");
    expect(fan).not.toContain("xG");
    expect(fan).toContain("Ring with a white centre: goal.");
    expect(shotRadius(0.4, false)).toBeGreaterThan(shotRadius(0.05, false));
    expect(shotRadius(0.4, true)).toBe(shotRadius(0.05, true));
  });

  it("speaks Chinese and Spanish", () => {
    expect(render(<ShotMap data={SHOTS} squads={SQUADS} />, "?lang=zh")).toContain("射门图");
    expect(render(<ShotMap data={SHOTS} squads={SQUADS} />, "?lang=es")).toContain("Mapa de tiros");
  });

  it("says so when there are no shots", () => {
    expect(render(<ShotMap data={{ ...SHOTS, shots: [] }} />)).toContain("No shots yet.");
  });
});

const HEAT: HeatmapReport = {
  match_id: "m1", up_to_t: 5400, period: null, source: "frames", cols: 3, rows: 2,
  teams: { home: { samples: 10, cells: [1, 0, 0.5, 0, 0.25, 0] }, away: { samples: 4, cells: [0, 0, 0, 0, 0, 1] } },
  players: [{ player_id: "h01", team: "home", samples: 6, cells: [1, 0, 0, 0, 0, 0] }],
};

describe("heatmap", () => {
  it("one square per busy cell, the team's or one player's", () => {
    expect(heatCells([1, 0, 0.5, 0, 0.25, 0], 3)).toEqual([[0, 0, 1], [2, 0, 0.5], [1, 1, 0.25]]);
    expect(render(<Heatmap data={HEAT} side="home" />).match(/class="viz-cell"/g)).toHaveLength(3);
    const keeper = render(<Heatmap data={HEAT} side="home" playerId="h01" squads={SQUADS} />);
    expect(keeper.match(/class="viz-cell"/g)).toHaveLength(1);
    expect(keeper).toContain("Heatmap of C. Okoro");
  });

  it("the analyst legend says where the counts come from; the fan one does not", () => {
    expect(render(<Heatmap data={HEAT} side="home" />)).toContain("10 player-seconds of tracking data");
    expect(render(<Heatmap data={{ ...HEAT, source: "events" }} side="home" />)).toContain("actions on the ball");
    expect(render(<Heatmap data={HEAT} side="home" />, "?lang=en&mode=fan")).toContain("the more time spent there");
  });
});

const NET: PassNetworkReport = {
  match_id: "m1", up_to_t: 5400, period: null, min_passes: 3,
  teams: {
    home: { source: "frames", nodes: [{ player_id: "h01", x: 8, y: 34, passes: 20, received: 5 },
                                      { player_id: "h05", x: 30, y: 20, passes: 40, received: 35 },
                                      { player_id: "h09", x: 75, y: 34, passes: 10, received: 22 }],
            edges: [{ from_id: "h05", to_id: "h09", passes: 9 }, { from_id: "h01", to_id: "h05", passes: 4 }] },
    away: { source: "frames", nodes: [], edges: [] },
  },
};

describe("pass network", () => {
  it("a line per pair and a numbered dot per starter, attacking right", () => {
    const html = render(<PassNetwork data={NET} side="home" squads={SQUADS} />);
    expect(html.match(/class="viz-edge"/g)).toHaveLength(2);
    expect(html.match(/class="viz-node/g)).toHaveLength(3);
    expect(html).toContain("B. Lind to A. Moreau: 9. A. Moreau to B. Lind: 0.");
    expect(html).toContain(`cx="${toPx(75, 34)[0]}"`);
    expect(html).toContain("3 or more completed passes");
  });

  it("adds both directions up per pair and ranks the most involved", () => {
    const pairs = pairsOf([{ from_id: "h09", to_id: "h05", passes: 3 }, { from_id: "h05", to_id: "h09", passes: 9 },
      { from_id: "h01", to_id: "h05", passes: 4 }]);
    expect(pairs[0]).toEqual({ a: "h05", b: "h09", ab: 9, ba: 3, passes: 12 });
    expect(pairs).toHaveLength(2);
    expect(hubsOf(NET.teams.home.nodes).map((h) => [h.id, h.n])).toEqual([["h05", 75], ["h09", 32], ["h01", 25]]);
  });

  it("analyst: a count on every line, a slider, the halves and the three most involved", () => {
    const html = render(<PassNetwork data={NET} side="home" squads={SQUADS} onPeriod={() => {}} />);
    expect(html.match(/class="viz-edge-n"/g)).toHaveLength(2);
    expect(html).toContain('type="range"');
    expect(html).toContain("Minimum passes to draw a line");
    expect(html).toContain("First half");
    expect(html).toContain("Most involved");
    expect(html.match(/class="viz-hub"/g)).toHaveLength(3);
    expect(html).toContain("75 passes");
  });

  it("fan: the top pairs named on the line, one sentence, others faded", () => {
    const html = render(<PassNetwork data={NET} side="home" squads={SQUADS} />, "?lang=en&mode=fan");
    expect(html).toContain("Most passes between B. Lind and A. Moreau (9)");
    expect(html).toContain("Lind and Moreau: 9");
    expect(html).not.toContain('type="range"');
    expect(html).not.toContain("Most involved");
    const zh = render(<PassNetwork data={NET} side="home" squads={SQUADS} />, "?lang=zh&mode=fan");
    expect(zh).toContain("配合最多的是 B. Lind 和 A. Moreau（9 次）");
  });

  it("an empty side says so", () => {
    expect(render(<PassNetwork data={NET} side="away" />)).toContain("No passes yet.");
  });
});

const POS: AveragePositionsReport = {
  match_id: "m1", up_to_t: 5400, period: null, players: [
    { player_id: "h09", team: "home", seconds: 5000, in_possession: { x: 80, y: 30 }, out_of_possession: { x: 60, y: 32 } },
    { player_id: "a10", team: "away", seconds: 5000, in_possession: { x: 70, y: 40 }, out_of_possession: { x: 50, y: 40 } },
    { player_id: "h05", team: "home", seconds: 120, in_possession: { x: 40, y: 20 }, out_of_possession: null },
  ],
};

describe("average positions", () => {
  it("both teams on one pitch, the away side flipped, short spells left out", () => {
    const html = render(<AveragePositions data={POS} squads={SQUADS} />);
    expect(html.match(/class="viz-node/g)).toHaveLength(2);
    expect(html).toContain(`cx="${toPx(80, 30)[0]}"`);
    expect(html).toContain(`cx="${toPx(70, 40, true)[0]}"`);
    expect(render(<AveragePositions data={POS} squads={SQUADS} phase="out_of_possession" />))
      .toContain(`cx="${toPx(60, 32)[0]}"`);
  });
});

describe("data hooks", () => {
  it("build the query: up_to rounded down, period, extra parameters", () => {
    expect(vizQuery()).toBe("");
    expect(vizQuery({ upTo: 1234 })).toBe("?up_to=1230");
    expect(vizQuery({ upTo: 1234, stepS: 1, period: 2 }, { min_passes: 5 })).toBe("?up_to=1234&period=2&min_passes=5");
    expect(vizPath("M seed", "pass-network", "?period=1")).toBe("/api/matches/M%20seed/pass-network?period=1");
  });

  it("VizBox shows a line while loading or after a failure", () => {
    expect(render(<VizBox state={{ data: null, loading: true, error: false }}>{() => null}</VizBox>)).toContain("Loading…");
    expect(render(<VizBox state={{ data: null, loading: false, error: true }}>{() => null}</VizBox>, "?lang=zh"))
      .toContain("没能加载");
  });

  it("VizBox says why a load failed and offers a Retry (Ax79)", () => {
    const failed = (fault: number | "offline", q?: string) =>
      render(<VizBox state={{ data: null, loading: false, error: true, fault, retry: () => {} }}>{() => null}</VizBox>, q);
    expect(failed(503)).toContain("error 503");
    expect(failed(503)).toContain(">Retry</button>");
    expect(failed("offline", "?lang=es")).toContain("Reintentar");
    expect(failed(404, "?lang=zh")).toContain("错误 404");
  });
});
