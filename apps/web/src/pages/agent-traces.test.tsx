// D10: the S4 agent trace list, fed the detect chains the live API served for M-seed-29. Rendered
// to static HTML like the other page tests; the fetch hook is covered through its sources.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentTrace, Match, Pivot1 as Pivot } from "@pivot/contracts";
import { toView } from "../data/live/provider";
import { MatchContext } from "../data/match";
import { fixtureTraceSource, groupChains, liveTraceSource, refMinute, type TraceState } from "../data/traces";
import { DEMO_TRACES } from "../fixtures/traces-1021";
import { SEED29_TRACES } from "../fixtures/traces-seed29";
import { PrefsProvider, type Lang } from "../i18n";
import { TraceList } from "./AgentTraces";

const side = (s: "home" | "away", name: string) => ({ name, short_name: name.slice(0, 3).toUpperCase(), side: s, color: "#000", squad: [] });
// The real periods of M-seed-29: four minutes of first-half stoppage, so elapsed 69 is 65′ on the clock.
const match = {
  match_id: "M-seed-29", clock: 6139, period: 2, status: "finished", speed: 1,
  home: side("home", "Harbour City"), away: side("away", "Northgate Rovers"),
  score: { home: 2, away: 1, home_penalties: null, away_penalties: null },
  periods: [{ period: 1, start_t: 0, end_t: 2945, added_minutes: 4 }, { period: 2, start_t: 2946, end_t: 6139, added_minutes: 8 }],
} as unknown as Match;

const pivot = (minute: number, headline: string, status: Pivot["status"] = "confirmed"): Pivot => ({
  pivot_id: `M-seed-29:p${minute}`, match_id: "M-seed-29", chain_id: `detect:M-seed-29:${minute}:d1`, minute, status,
  direction: "home", severity: 3, trigger_event_ids: [],
  narrative: { chain_id: null, headline, verifier_attempts: 1, source: status === "degraded" ? "template" : "llm",
    prefs: { audience: "analyst", language: "en", focus_team: null, focus_player_id: null }, sentences: [] },
} as unknown as Pivot);

const PIVOTS = [
  pivot(89, "Anlitesov's goal shifts momentum late"),
  pivot(69, "Harbour City drops line and press"),
  pivot(39, "A card changes the game", "degraded"),
];

// PrefsProvider reads the language from `?lang=`, so the language tests give it a window to read.
const g = globalThis as { window?: unknown };
afterEach(() => {
  delete g.window;
});

function page(state: TraceState, { at = "/trace", lang = "en" as Lang, pivots = PIVOTS, clock = match.clock } = {}) {
  g.window = { location: { search: `?lang=${lang}` }, localStorage: { getItem: () => null, setItem: () => {} } };
  const view = toView({ match: { ...match, clock }, events: [], metrics: [], pivots });
  return renderToStaticMarkup(
    <PrefsProvider>
      <MemoryRouter initialEntries={[at]}>
        <MatchContext.Provider value={view}>
          <Routes>
            <Route path="/trace" element={<TraceList state={state} onRetry={() => {}} />} />
            <Route path="/trace/:id" element={<TraceList state={state} pivotId={at.split("/").pop()} onRetry={() => {}} />} />
          </Routes>
        </MatchContext.Provider>
      </MemoryRouter>
    </PrefsProvider>,
  );
}

const ready = (traces = SEED29_TRACES): TraceState => ({ kind: "ready", chains: groupChains(traces) });
const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

describe("grouping the trace into chains", () => {
  it("reads p39 from the live API: three rejections, two rewrites, then the template", () => {
    const [p89, p69, p39] = groupChains(SEED29_TRACES);
    expect([p89.pivotId, p69.pivotId, p39.pivotId]).toEqual(["M-seed-29:p89", "M-seed-29:p69", "M-seed-29:p39"]);
    expect(p39.steps.map((s) => s.agent)).toEqual(
      ["judge", "explainer", "verifier", "explainer", "verifier", "explainer", "verifier", "template"]);
    expect(p39).toMatchObject({ outcome: "degraded", rewrites: 2, template: true });
    expect(p39.rejections.map((i) => i.code)).toEqual(["number_mismatch", "schema_invalid", "schema_invalid"]);
    expect(p69).toMatchObject({ outcome: "confirmed", rewrites: 0, template: false, rejections: [] });
  });

  it("keeps What-if chains out and sorts steps that arrive out of order", () => {
    const whatif = { ...SEED29_TRACES[0], chain_id: "whatif:M-seed-29:s1", trace_id: "w:0", agent: "executor" as const };
    const shuffled = [...SEED29_TRACES].reverse();
    const chains = groupChains([whatif, ...shuffled]);
    expect(chains).toHaveLength(3);
    expect(chains[2].steps.map((s) => s.step)).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
  });

  it("reads the Judge's rejection in the fixture as not a pivot", () => {
    const rejected = groupChains(DEMO_TRACES).find((c) => c.outcome === "rejected")!;
    expect(rejected.steps).toHaveLength(1);
    expect(refMinute(rejected.pivotId)).toBe(51);
    expect(refMinute("pv-63")).toBeNull();
  });
});

describe("S4 agent trace page", () => {
  it("shows each step, the reasons, the rewrites and the template, on the match clock", () => {
    const html = page(ready());
    const shown = text(html);
    expect(shown).toContain("65′ · Harbour City drops line and press");  // elapsed 69, after 4′ of stoppage
    expect(shown).toContain("85′ · Anlitesov");
    expect(shown).toContain("40′ · A card changes the game");   // elapsed 39 is the 40th minute
    expect(shown).toContain("Template summary");
    expect(shown).toContain("Rewrites: 2");
    expect(shown).toContain("Final text: template");
    expect(shown).toContain("Sent back by the Verifier (3)");
    expect(shown).toContain("Number does not match: The number 10 in sentence 1 has no matching claim.");
    expect(shown).toContain("Malformed output: 1 schema errors: Input should be");
    expect(shown).not.toMatch(/Malformed output: [^<]*field_tilt_pct'? Malformed/);  // cut in the list, whole in the verdict
    expect(shown).toContain("Turning point · severity 3");
    expect(shown).toContain("Rewrite 2");
    expect(shown).toContain("Template wrote the summary");
    expect(html.match(/class="trace-step"/g)).toHaveLength(10);       // p69 and p89 three each, p39 four
    expect(html.match(/class="trace-step bad"/g)).toHaveLength(4);    // p39: three rejections and the template
    expect(html.match(/Verified/g)).toHaveLength(2);
  });

  it("writes the worker's fixed lines in the page's language and marks the AI's own words (Ax31)", () => {
    const base = SEED29_TRACES[0];
    const step = (n: number, agent: AgentTrace["agent"], output_summary: string, status: AgentTrace["status"] = "ok") =>
      ({ ...base, chain_id: "detect:M-seed-29:69:d1", trace_id: `x:${n}`, step: n, agent, output_summary, status, verdict: null });
    const traces = [
      step(0, "judge", "is_pivot=true severity=2: Harbour City dropped deeper and lost the ball more."),
      step(1, "explainer", "unavailable: TimeoutError", "error"),
      step(2, "template", "Harbour City change shifts the balance", "degraded"),
    ];
    const zh = text(page(ready(traces), { lang: "zh" }));
    expect(zh).toContain("模型没有回应（TimeoutError）");
    expect(zh).not.toContain("unavailable:");
    expect(zh).toContain("Harbour City dropped deeper and lost the ball more. 原文");
    const en = text(page(ready(traces)));
    expect(en).toContain("The model did not answer (TimeoutError)");
    expect(en).not.toContain(" original");
  });

  it("speaks Chinese and Spanish", () => {
    const zh = text(page(ready(), { lang: "zh" }));
    expect(zh).toContain("AI 工作记录");
    expect(zh).toContain("重写 2 次");
    expect(zh).toContain("最终文字：模板");
    expect(zh).toContain("核对员打回的原因（3）");
    expect(zh).toContain("数字对不上");
    const es = text(page(ready(), { lang: "es" }));
    expect(es).toContain("Reescrituras: 2");
    expect(es).toContain("Verificador");
  });

  it("shows one pivot's trace with a way back to it", () => {
    const one = groupChains(SEED29_TRACES).filter((c) => c.pivotId === "M-seed-29:p39");
    const shown = text(page({ kind: "ready", chains: one }, { at: "/trace/M-seed-29:p39" }));
    expect(shown).toContain("← Pivot 40′");
    expect(shown).toContain("All turning points");
    expect(shown).not.toContain("65′");
  });

  it("hides chains the replay has not reached yet, a turned-down candidate included", () => {
    const shown = text(page(ready(DEMO_TRACES), { pivots: [], clock: 50 * 60 }));
    expect(shown).toContain("No agent activity yet");
    const later = text(page(ready(DEMO_TRACES), { pivots: [], clock: 52 * 60 }));
    expect(later).toContain("47′ · Candidate");             // elapsed 51, two minutes into the second half
    expect(later).toContain("Not a pivot");
    expect(later).not.toContain("Final text");
    expect(later).not.toContain("Rewrites");
  });

  it("has loading, error and empty states", () => {
    expect(page({ kind: "loading" })).toContain('aria-busy="true"');
    expect(text(page({ kind: "loading" }))).toContain("Loading the agent trace");
    const failed = page({ kind: "error", error: new Error("x") });
    expect(failed).toContain('role="alert"');
    expect(text(failed)).toContain("Retry now");
    expect(text(page({ kind: "ready", chains: [] }, { at: "/trace/M-seed-29:p40" }))).toContain(
      "No agent activity recorded for this turning point yet.");
  });
});

describe("trace sources", () => {
  afterEach(() => vi.unstubAllGlobals());

  const respond = (status: number, body: unknown) =>
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })));

  it("asks the API for a pivot's chains and treats 404 as no record", async () => {
    respond(200, SEED29_TRACES.slice(0, 3));
    await expect(liveTraceSource.pivot("M-seed-29:p69")).resolves.toHaveLength(3);
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe("/api/pivots/M-seed-29%3Ap69/traces");
    respond(404, { detail: "not found" });
    await expect(liveTraceSource.pivot("M-seed-29:p40")).resolves.toEqual([]);
    respond(500, { detail: "boom" });
    await expect(liveTraceSource.match("M-seed-29")).rejects.toThrow("500");
  });

  it("serves the fixture by whole input_ref", async () => {
    expect((await fixtureTraceSource.pivot("pv-63")).map((t) => t.agent)).toEqual(
      ["judge", "explainer", "verifier", "explainer", "verifier"]);
  });
});
