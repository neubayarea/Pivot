// C05: the What-if Lab. Chips with their reasons, a run from queued to result, the failed state,
// and the mock behind `?fixture=1`. Rendered to static HTML, like states.test, so no DOM is needed.
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import type { MatchEvent, Pivot1 as Pivot, Scenario } from "@pivot/contracts";
import { ApiError } from "../data/live/api";
import { publishScenario } from "../data/live/scenarioFeed";
import { FixtureContext, MatchContext, computeStats, type MatchView } from "../data/match";
import { mockOptions, mockScenarioApi, resetMockScenarios, wilson } from "../data/scenarioMock";
import {
  OUTCOMES, biggestShift, cacheKey, optionLabel, progressOf, runScenario, type RunState, type ScenarioApi, type ScenarioOption,
} from "../data/scenarios";
import { translator } from "../i18n";
import WhatIfLab from "../pages/WhatIfLab";
import { ArmCompare, RunFailed, RunProgress, ScenarioChips, ScenarioResult, failureText, scoreDashes, storyLine } from "./WhatIf";

const ev = (id: string, minute: number, team: "home" | "away", type: MatchEvent["type"], extra: Partial<MatchEvent> = {}) =>
  ({ event_id: id, seq: minute, t: minute * 60, minute, period: minute < 45 ? 1 : 2, team, type, meta: {}, shot_outcome: null, ...extra }) as MatchEvent;

const pivot: Pivot = {
  pivot_id: "p63", match_id: "m1", chain_id: "c", minute: 63, status: "confirmed", direction: "away", severity: 3,
  trigger_event_ids: ["sub62"],
  narrative: { chain_id: null, headline: "Substitution flipped the left flank", verifier_attempts: 1, source: "llm",
    prefs: { audience: "analyst", language: "en", focus_team: null, focus_player_id: null },
    sentences: [{ text: "x", claims: [], evidence_ids: ["sub62"], context_ids: [] }] },
};

/** A match with a 41′ home goal, a 63′ home substitution and a 71′ away goal; no red card. */
function matchView(events: MatchEvent[] = [
  ev("g41", 40, "home", "shot", { shot_outcome: "goal" }),
  ev("sub62", 62, "home", "substitution"),
  ev("g70", 70, "away", "shot", { shot_outcome: "goal" }),
]): MatchView {
  const team = (side: "home" | "away", name: string, short: string) => ({ name, short_name: short, side, color: "#000" });
  const newestFirst = events.slice().reverse();
  return {
    match: { match_id: "m1", clock: 4500, period: 2, status: "live", speed: 1, clockLabel: "75:00",
      score: { home: 1, away: 1, home_penalties: null, away_penalties: null } },
    teams: { home: team("home", "Harbour City", "HCY"), away: team("away", "Northvale", "NVR") },
    events: newestFirst, metrics: [], pivots: [pivot], stats: computeStats([]), squads: { home: [], away: [] },
    playerName: (id) => id ?? "", eventById: (id) => events.find((e) => e.event_id === id),
    pivotDetail: (id) => (id === pivot.pivot_id ? { pivot, window: [3660, 3900], frames: [], beforeAfter: [] } : undefined),
    playback: null,
  };
}

const render = (node: ReactNode) => renderToStaticMarkup(<MemoryRouter>{node}</MemoryRouter>);
const en = translator("en");

/** A clock that moves on half a second every time the mock looks at it. */
function steppingClock(step = 500) {
  let now = 0;
  return () => (now += step);
}

beforeEach(() => resetMockScenarios());

describe("scenario chips", () => {
  const view = matchView();
  const options = mockOptions(view, "p63");

  it("lists the catalog with the pivot's own substitution first and unavailable ones last", () => {
    expect(options.map((o) => [o.type, o.enabled])).toEqual([
      ["cancel_substitution", true], ["move_substitution", true], ["remove_goal", true], ["change_press", true], ["remove_red_card", false],
    ]);
    expect(options[0]).toMatchObject({ label: "Cancel 63′ substitution", target_event_id: "sub62", at_minute: 62, team: "home" });
    expect(options.find((o) => o.type === "remove_goal")?.label).toBe("Disallow 71′ goal");
    expect(options.find((o) => o.type === "change_press")).toMatchObject({ team: "home", label: "Press higher from 64′" });
  });

  it("names the changes this match cannot have on one line, with why, instead of a dead button (C13)", () => {
    const html = render(<ScenarioChips options={options} selected="cancel_substitution" onSelect={() => {}} teams={view.teams} />);
    expect(html).toContain("No red card in this match");
    expect(html).toMatch(/class="scn-off">Not possible here: Remove red card \(No red card in this match\)/);
    expect(html).not.toContain('aria-disabled="true"');
    expect(html).not.toContain(" disabled=");
    expect(html.match(/aria-pressed="true"/g)).toHaveLength(1);
    expect(html).toContain("Remove red card");
  });

  it("reads in the viewer's language, the reason too", () => {
    const zh = translator("zh");
    expect(optionLabel(options[0], zh)).toBe("取消 63′ 的换人");
    expect(optionLabel(options[1], zh, 80)).toBe("把换人改到 80′");
    const off = options.find((o) => !o.enabled)!;
    const html = renderToStaticMarkup(<ScenarioChips options={[off]} selected={null} onSelect={() => {}} teams={view.teams} />);
    expect(html).toContain("No red card in this match");
    // Unknown types keep the API's own label.
    expect(optionLabel({ ...options[0], type: "change_formation", label: "Switch to 3-5-2" } as ScenarioOption, zh)).toBe("Switch to 3-5-2");
  });
});

describe("a run from queued to result", () => {
  it("polls until it completes, the bar filling on the way", async () => {
    const view = matchView();
    const source = mockScenarioApi(() => ({ view, lang: "en" }), steppingClock());
    const seen: Scenario[] = [];
    const final = await runScenario(source, { pivot_id: "p63", type: "cancel_substitution", n_runs: 200 },
      { signal: new AbortController().signal, pollMs: 1, onUpdate: (s) => seen.push(s) });
    expect(seen[0]).toMatchObject({ status: "queued", done: 0 });
    expect(seen.some((s) => s.status === "running" && s.done > 0 && s.done < 400)).toBe(true);
    const progress = seen.map(progressOf);
    expect(progress).toEqual([...progress].sort((a, b) => a - b));
    expect(final.status).toBe("completed");
    expect(final.done).toBe(400);
    expect(final.result?.narrative?.sentences.length).toBeGreaterThan(0);
  });

  it("shows the replays done out of 2 × n_runs", () => {
    const running = { status: "running", done: 120, spec: { n_runs: 200 } } as Scenario;
    const html = render(<RunProgress scenario={running} />);
    expect(html).toContain("Replaying");
    expect(html).toContain("120 of 400 replays");
    expect(html).toContain('aria-valuenow="120"');
    expect(html).toContain("width:30%");
    expect(render(<RunProgress scenario={null} />)).toContain("Starting");
  });

  it("puts the two distributions side by side with their ranges, the narrative and the stamp", async () => {
    const view = matchView();
    const source = mockScenarioApi(() => ({ view, lang: "en" }), steppingClock(10_000));
    const body = { pivot_id: "p63", type: "cancel_substitution" as const, n_runs: 1000 as const };
    const scenario = await runScenario(source, body, { signal: new AbortController().signal, pollMs: 1, onUpdate: () => {} });
    const state = { phase: "done", body, scenario, cached: false } as Extract<RunState, { phase: "done" }>;
    const html = render(<ScenarioResult state={state} option={mockOptions(view, "p63")[0]} teams={view.teams} onReset={() => {}} source={source} />);
    expect(html).toContain("Simulated, 1,000 replays");
    expect(html).toContain("As played (from 63′)");
    expect(html).toContain("With the change: Cancel 63′ substitution");
    expect(html).toMatch(/HCY \d+% \(\d+–\d+\)/);
    expect(html).toContain("Clear difference");
    expect(html).toContain("◆");
    expect(html).toMatch(/<b>Win chance for Harbour City up \d+ points<\/b>/);
    expect(html).toContain("Try another");
    expect(html).not.toContain("simulated before");
    const cached = render(<ScenarioResult state={{ ...state, cached: true }} option={undefined} teams={view.teams} onReset={() => {}} source={source} />);
    expect(cached).toContain("Instant: simulated before");
  });

  it("names the outcome that moved most, and says so when the ranges still overlap", () => {
    const d = (h: number, dr: number, a: number) => ({ home_win: h, draw: dr, away_win: a, home_advance: null, ci95: {} });
    expect(biggestShift({ baseline: d(0.5, 0.3, 0.2), counterfactual: d(0.4, 0.3, 0.3), significant: {} }))
      .toEqual({ outcome: "home_win", points: -10, significant: false });
    expect(biggestShift({ baseline: d(0.5, 0.3, 0.2), counterfactual: d(0.4, 0.28, 0.32), significant: { away_win: true } }))
      .toMatchObject({ outcome: "away_win", points: 12, significant: true });
  });

  it("moves the bar on a pushed update, without waiting for the next poll", async () => {
    let gets = 0;
    const base = { scenario_id: "m1:s9", match_id: "m1", status: "queued", done: 0, result: null, spec: { n_runs: 200 } } as unknown as Scenario;
    const source: ScenarioApi = {
      options: async () => [],
      start: async () => base,
      get: async () => (++gets > 1 ? { ...base, status: "failed" } : base),
    };
    const seen: number[] = [];
    const run = runScenario(source, { pivot_id: "p63", type: "cancel_substitution" },
      { signal: new AbortController().signal, pollMs: 20, onUpdate: (s) => seen.push(s.done) });
    await Promise.resolve();
    await Promise.resolve();
    publishScenario({ scenario_id: "m1:s9", done: 150, status: "running" });
    publishScenario({ scenario_id: "other", done: 399 });
    await run;
    expect(seen).toContain(150);
    expect(seen).not.toContain(399);
  });
});

describe("failed runs", () => {
  it("settles on failed when the API says so", async () => {
    const queued = { scenario_id: "s1", status: "queued", done: 0, result: null, spec: { n_runs: 200 } } as unknown as Scenario;
    const source: ScenarioApi = { options: async () => [], start: async () => queued, get: async () => ({ ...queued, status: "failed", done: 37 }) };
    const s = await runScenario(source, { pivot_id: "p", type: "remove_goal" }, { signal: new AbortController().signal, pollMs: 1, onUpdate: () => {} });
    expect(s).toMatchObject({ status: "failed", done: 37 });
  });

  it("gives up after a few failed polls in a row, but rides out one", async () => {
    const queued = { scenario_id: "s1", status: "queued", done: 0, result: null, spec: { n_runs: 200 } } as unknown as Scenario;
    let calls = 0;
    const flaky: ScenarioApi = { options: async () => [], start: async () => queued, get: async () => {
      if (++calls === 1) throw new TypeError("network");
      return { ...queued, status: "failed" };
    } };
    await expect(runScenario(flaky, { pivot_id: "p", type: "remove_goal" }, { signal: new AbortController().signal, pollMs: 1, onUpdate: () => {} }))
      .resolves.toMatchObject({ status: "failed" });
    const down: ScenarioApi = { ...flaky, get: async () => { throw new ApiError(503, "down", false); } };
    await expect(runScenario(down, { pivot_id: "p", type: "remove_goal" }, { signal: new AbortController().signal, pollMs: 1, onUpdate: () => {} }))
      .rejects.toBeInstanceOf(ApiError);
  });

  it("offers a retry and another scenario, with a reason the viewer can act on", () => {
    const html = render(<RunFailed error={null} onRetry={() => {}} onReset={() => {}} />);
    expect(html).toContain('role="alert"');
    expect(html).toContain("The simulation did not finish");
    expect(html).toContain("Run again");
    expect(html).toContain("Try another");
    expect(failureText(new ApiError(422, "x"), en)).toContain("(422)");
    expect(failureText(new ApiError(502, "x"), en)).toContain("Could not reach the server");
    expect(failureText(new TypeError("Failed to fetch"), en)).toContain("Could not reach the server");
  });
});

describe("mock mode (?fixture=1)", () => {
  it("refuses a chip that is greyed out, a bad run count or minute, like the API", async () => {
    const view = matchView();
    const source = mockScenarioApi(() => ({ view, lang: "en" }));
    await expect(source.start({ pivot_id: "p63", type: "remove_red_card" })).rejects.toMatchObject({ status: 422 });
    await expect(source.start({ pivot_id: "p63", type: "remove_goal", n_runs: 300 as 200 })).rejects.toMatchObject({ status: 422 });
    await expect(source.start({ pivot_id: "p63", type: "move_substitution", params: { new_minute: 20 } })).rejects.toMatchObject({ status: 422 });
    await expect(source.options("nope")).rejects.toMatchObject({ status: 404 });
    await expect(source.get("nope")).rejects.toMatchObject({ status: 404 });
  });

  it("gives realistic shares that add up, with Wilson ranges around them, the same every time", async () => {
    const view = matchView();
    const run = async () => {
      resetMockScenarios();
      const source = mockScenarioApi(() => ({ view, lang: "en" }), steppingClock(10_000));
      return runScenario(source, { pivot_id: "p63", type: "remove_goal" }, { signal: new AbortController().signal, pollMs: 1, onUpdate: () => {} });
    };
    const a = await run();
    for (const d of [a.result!.baseline, a.result!.counterfactual]) {
      expect(OUTCOMES.reduce((s, k) => s + d[k], 0)).toBeCloseTo(1, 9);
      for (const k of OUTCOMES) {
        const [lo, hi] = d.ci95[k];
        expect(lo).toBeLessThanOrEqual(d[k]);
        expect(hi).toBeGreaterThanOrEqual(d[k]);
      }
    }
    // Disallowing Northvale's equaliser leaves Harbour City ahead: their win share goes up.
    expect(a.result!.counterfactual.home_win).toBeGreaterThan(a.result!.baseline.home_win);
    expect((await run()).result).toEqual(a.result);
    const [lo, hi] = wilson(34, 100);
    expect(lo).toBeCloseTo(0.2546, 3);
    expect(hi).toBeCloseTo(0.4372, 3);
  });

  it("answers the same question again at once, as the API's store does", async () => {
    const view = matchView();
    const source = mockScenarioApi(() => ({ view, lang: "en" }), steppingClock(10_000));
    const body = { pivot_id: "p63", type: "change_press" as const };
    const first = await runScenario(source, body, { signal: new AbortController().signal, pollMs: 1, onUpdate: () => {} });
    const again = await source.start(body);
    expect(again).toMatchObject({ scenario_id: first.scenario_id, status: "completed" });
    expect(cacheKey({ ...body, n_runs: 200, params: { b: 1, a: 2 } })).toBe(cacheKey({ ...body, params: { a: 2, b: 1 } }));
  });

  it("writes the comparison in the viewer's language", async () => {
    const view = matchView();
    const source = mockScenarioApi(() => ({ view, lang: "es" }), steppingClock(10_000));
    const s = await runScenario(source, { pivot_id: "p63", type: "cancel_substitution" }, { signal: new AbortController().signal, pollMs: 1, onUpdate: () => {} });
    expect(s.result!.narrative!.prefs.language).toBe("es");
    expect(s.result!.narrative!.sentences[0].text).toContain("Anular el cambio del 63′");
  });

  it("renders the page for a pivot: where it came from, the stamp, the chips loading", () => {
    const view = matchView();
    const page = (path: string) => renderToStaticMarkup(
      <MemoryRouter initialEntries={[path]}>
        <FixtureContext.Provider value>
          <MatchContext.Provider value={view}>
            <Routes><Route path="/whatif/:id" element={<WhatIfLab />} /></Routes>
          </MatchContext.Provider>
        </FixtureContext.Provider>
      </MemoryRouter>,
    );
    const html = page("/whatif/p63");
    expect(html).toContain('href="/pivot/p63"');
    expect(html).toContain("Pivot 64′: Substitution flipped the left flank");   // elapsed minute 63
    expect(html).toContain("Simulated, not a prediction");
    expect(html).toContain("Loading the scenarios…");
    expect(html).toContain("Pick a scenario to set up the replay.");
    expect(page("/whatif/nope")).toContain("Pivot not found");
  });
});

describe("the result as a story, with the two arms side by side (Ax51)", () => {
  const d = (h: number, dr: number, a: number) => ({ home_win: h, draw: dr, away_win: a, home_advance: null, ci95: {} });
  const spread = (mean: number) => ({ mean, sd: 0, p10: mean, p90: mean });
  const side = (shots: number, on: number, xg: number, red: number) => ({
    goals: spread(1), shots: spread(shots), shots_on_target: spread(on), xg: spread(xg), possession_pct: spread(50),
    cards: spread(red), red_cards: spread(red), scored_share: 0.5,
  });
  const arm = (scores: [number, number, number][], home: ReturnType<typeof side>, away: ReturnType<typeof side>) => ({
    n_runs: 200, from_t: 38 * 60, top_scores: scores.map(([h, a, share]) => ({ home: h, away: a, share })), home, away,
  });
  const withStats = {
    baseline: d(0.82, 0.12, 0.06), counterfactual: d(0.46, 0.3, 0.24), significant: { home_win: true },
    baseline_stats: arm([[3, 1, 0.21], [2, 1, 0.18], [3, 0, 0.12], [4, 1, 0.08]], side(9.4, 3.2, 1.21, 0.02), side(2.1, 0.6, 0.18, 0.31)),
    counterfactual_stats: arm([[1, 1, 0.19], [2, 1, 0.15], [1, 0, 0.11]], side(5.3, 1.9, 0.62, 0.05), side(4.8, 1.7, 0.57, 0.04)),
  };
  const teams = matchView().teams;
  const input = { result: withStats, type: "remove_red_card", minute: "38", change: "Remove 38′ red card", teams };

  it("tells it in a sentence built from the result's own numbers, in every language", () => {
    expect(storyLine(input, en)).toBe(
      "Without the 38′ red card, the chance of Harbour City winning falls from 82% to 46%, and the most likely score goes from 3–1 to 1–1.");
    expect(storyLine(input, translator("zh"))).toBe("如果没有 38′ 这张红牌，Harbour City 赢球的机会从 82% 掉到 46%，最常见的比分从 3–1 变成 1–1。");
    expect(storyLine(input, translator("es"))).toBe(
      "Sin la roja del 38′, las opciones de victoria de Harbour City bajan del 82% al 46%, y el resultado más probable pasa de 3–1 a 1–1.");
  });

  it("drops the score for a result stored before the stats, and names other changes plainly", () => {
    const old = { ...input, result: { ...withStats, baseline_stats: null, counterfactual_stats: undefined } };
    expect(storyLine(old, en)).toBe("Without the 38′ red card, the chance of Harbour City winning falls from 82% to 46%.");
    expect(storyLine({ ...input, type: "change_press", pressLower: true }, translator("zh"))).toMatch(/^如果从 38′ 起压得更低，/);
    expect(storyLine({ ...input, type: "change_formation", change: "Switch to 3-5-2" }, en)).toMatch(/^With the change \(Switch to 3-5-2\), /);
    const same = { ...input, result: { ...withStats, counterfactual_stats: { ...withStats.counterfactual_stats, top_scores: withStats.baseline_stats.top_scores } } };
    expect(storyLine(same, en)).toMatch(/and the most likely score stays 3–1\.$/);
  });

  it("lists the top three scores and each side's shots, on target, xG and red cards from the saved minute", () => {
    const html = render(<ArmCompare was={withStats.baseline_stats} now={withStats.counterfactual_stats} teams={teams} from="38" />);
    expect(html).toContain("From 38′ to the final whistle");
    expect(html).toContain("HCY – NVR");
    expect(html.match(/<li /g)).toHaveLength(6);               // three per arm; 4–1 is left out
    expect(html).not.toContain("4–1");
    expect(html).toContain('aria-label="3–1 in 21% of replays"');
    expect(html).toContain("9.4 – 2.1");                         // shots
    expect(html).toContain("1.9 – 1.7");                         // on target, with the change
    expect(html).toContain("1.21 – 0.18");                       // xG
    expect(html).toContain("0.02 – 0.31");                       // red cards
  });

  it("leaves the comparison out of a result without stats", async () => {
    const view = matchView();
    const source = mockScenarioApi(() => ({ view, lang: "en" }), steppingClock(10_000));
    const body = { pivot_id: "p63", type: "cancel_substitution" as const, n_runs: 200 as const };
    const scenario = await runScenario(source, body, { signal: new AbortController().signal, pollMs: 1, onUpdate: () => {} });
    const state = { phase: "done", body, scenario, cached: false } as Extract<RunState, { phase: "done" }>;
    const props = { option: mockOptions(view, "p63")[0], teams: view.teams, onReset: () => {}, source };
    const plain = render(<ScenarioResult state={state} {...props} />);
    expect(plain).not.toContain("Side by side");
    expect(plain).toMatch(/Without the 63′ substitution, the chance of Harbour City winning (rises|falls) from \d+% to \d+%\./);
    const rich = { ...state, scenario: { ...scenario, result: { ...scenario.result!, ...withStats } } };
    const html = render(<ScenarioResult state={rich} {...props} />);
    expect(html).toContain("Side by side");
    expect(html).toContain("and the most likely score goes from 3–1 to 1–1.");
  });
});

describe("what-if typography (C13 QA)", () => {
  it("writes scores with an en dash and leaves formations alone", () => {
    expect(scoreDashes("from 1-2 to 2-2")).toBe("from 1–2 to 2–2");
    expect(scoreDashes("a 4-3-3 shape")).toBe("a 4-3-3 shape");
    expect(scoreDashes("Remove 38' red card, at 90'.")).toBe("Remove 38′ red card, at 90′.");
  });
});
