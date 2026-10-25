// Cx3: on live data the S2 timeline widens to cover the pivot's evidence, and no gold tick is ever
// drawn past the ends of the track. Rendered to static HTML, like states.test, so no DOM is needed.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { Match, MatchEvent, Pivot1 as Pivot } from "@pivot/contracts";
import Scrubber from "../components/Scrubber";
import { toView } from "../data/live/provider";
import { MatchContext } from "../data/match";
import { evidenceWindow } from "../data/window";
import PivotDetail from "./PivotDetail";

const ev = (id: string, t: number, type: MatchEvent["type"] = "shot") =>
  ({ event_id: id, seq: Math.round(t / 10), t, minute: Math.floor(t / 60), period: 2, team: "home", type, meta: {},
    shot_outcome: null, location: [80, 34] }) as unknown as MatchEvent;

const side = (s: "home" | "away") => ({ name: s, short_name: s.toUpperCase(), side: s, color: "#000", squad: [] });
const match = {
  match_id: "m1", clock: 4200, period: 2, status: "live", speed: 1, home: side("home"), away: side("away"),
  score: { home: 0, away: 0, home_penalties: null, away_penalties: null },
} as unknown as Match;

const pivot = (evidence: string[]): Pivot => ({
  pivot_id: "p61", match_id: "m1", chain_id: "c", minute: 61, status: "confirmed", direction: "home", severity: 2,
  trigger_event_ids: [],
  narrative: { chain_id: null, headline: "Late press", verifier_attempts: 1, source: "llm",
    prefs: { audience: "analyst", language: "en", focus_team: null, focus_player_id: null },
    sentences: [{ text: "They pressed and shot.", claims: [], evidence_ids: evidence, context_ids: [] }] },
} as unknown as Pivot);

/** S2 for pivot p61 with the given events, through the same live view the API feeds. */
function detailPage(events: MatchEvent[], evidence = events.map((e) => e.event_id)) {
  const view = toView({ match, events, metrics: [], pivots: [pivot(evidence)] });
  const html = renderToStaticMarkup(
    <MemoryRouter initialEntries={["/pivot/p61"]}>
      <MatchContext.Provider value={view}>
        <Routes>
          <Route path="/pivot/:id" element={<PivotDetail />} />
        </Routes>
      </MatchContext.Provider>
    </MemoryRouter>,
  );
  return { view, html };
}

/** Left offsets (percent) of every tick on the track: gold evidence ticks and the red pivot tick. */
const ticks = (html: string) =>
  [...html.matchAll(/class="(?:mk|pv-mk)[^"]*" style="left:([-\d.e]+)%"/g)].map((m) => Number(m[1]));

describe("pivot detail timeline window", () => {
  it("widens past the default two minutes to cover a 64′ shot on a 61′ pivot", () => {
    const { view, html } = detailPage([ev("press", 60 * 60 + 50, "pressure"), ev("shot", 64 * 60 + 12)]);
    const [from, to] = view.pivotDetail("p61")!.window;
    expect(from).toBe(59 * 60);
    expect(to).toBe(65 * 60);                      // the old window stopped at 63′
    expect(to).toBeGreaterThanOrEqual(64 * 60 + 12);
    const at = ticks(html);
    expect(at).toHaveLength(3);                     // two evidence ticks and the pivot
    expect(at.every((left) => left >= 0 && left <= 100)).toBe(true);
    expect(html).toContain("59′–65′");
    expect(html).not.toContain("outside the timeline");
  });

  it("stops six minutes from the pivot and labels evidence it still cannot reach", () => {
    const { view, html } = detailPage([ev("goal", 80 * 60), ev("shot", 61 * 60 + 20)]);
    const [from, to] = view.pivotDetail("p61")!.window;
    expect([from, to]).toEqual([59 * 60, 67 * 60]);
    const at = ticks(html);
    expect(at).toHaveLength(2);                     // the 80′ goal gets no tick
    expect(at.every((left) => left >= 0 && left <= 100)).toBe(true);
    expect(html.match(/outside the timeline/g)).toHaveLength(2);    // its chip and, as it is picked, the caption
    expect(html).toMatch(/class="ev on out"[^>]*>#480/);
    expect(html).toContain('value="4020"');           // the clock starts at the window's edge, not at 80′
  });

  it("keeps two minutes either side when the evidence is all close", () => {
    expect(evidenceWindow(61, [61 * 60 + 5])).toEqual([59 * 60, 63 * 60]);
    expect(evidenceWindow(61, [])).toEqual([59 * 60, 63 * 60]);
    expect(evidenceWindow(1, [10])).toEqual([0, 3 * 60]);
  });

  it("the scrubber never draws a tick outside its window", () => {
    const html = renderToStaticMarkup(
      <Scrubber window={[100, 200]} t={150} onChange={() => {}} playing={false} onPlayingChange={() => {}}
        pivotMinutes={[5]} marks={[{ t: 50, on: false }, { t: 150, on: true }, { t: 260, on: false }]} />,
    );
    expect(ticks(html)).toEqual([50]);
  });
});
