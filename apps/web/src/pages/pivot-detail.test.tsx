// Cx3: on live data the S2 timeline widens to cover the pivot's evidence, and no gold tick is ever
// drawn past the ends of the track. Rendered to static HTML, like states.test, so no DOM is needed.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { Match, MatchEvent, Pivot1 as Pivot, TrackingFrame } from "@pivot/contracts";
import Pitch, { whoFromSquads } from "../components/Pitch";
import Scrubber from "../components/Scrubber";
import { toView } from "../data/live/provider";
import { MatchContext } from "../data/match";
import { evidenceWindow } from "../data/window";
import PivotDetail, { detailFrame } from "./PivotDetail";

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

// Ax25: on live data the S2 pitch draws the API's tracking frames, like the pitch board.
describe("pivot detail pitch", () => {
  const empty = { match_id: "m1", period: 2, t: 59 * 60, possession: null, players: [], ball: { owner_id: null, x: 52.5, y: 34, z: 0 } } as TrackingFrame;
  const tracked = (t: number) => ({
    ...empty, t, ball: { owner_id: "h09", x: 70, y: 30, z: 0 },
    players: [{ player_id: "h09", x: 70, y: 30 }, { player_id: "a04", x: 72, y: 31 }],
  }) as unknown as TrackingFrame;

  it("draws the fetched frame when the detail has no players of its own", () => {
    const got = detailFrame([empty], 59 * 60, 61 * 60, { frame: tracked(61 * 60), missing: false });
    expect(got.note).toBeNull();
    expect(got.frame.players).toHaveLength(2);
    expect(got.frame.t).toBe(61 * 60);
  });

  it("keeps the fixture's own frames", () => {
    const own = [tracked(100), tracked(101)];
    const got = detailFrame(own, 100, 101, { frame: tracked(999), missing: false });
    expect(got.frame).toBe(own[1]);
  });

  it("says when the positions are loading or the match has none, and keeps the clock", () => {
    expect(detailFrame([empty], 59 * 60, 3700, { frame: null, missing: false })).toMatchObject({ note: "loading", frame: { t: 3700, players: [] } });
    expect(detailFrame([empty], 59 * 60, 3700, { frame: null, missing: true }).note).toBe("none");
  });

  it("shows an empty-state note, not an error, on a match with no tracking", () => {
    const { html } = detailPage([ev("shot", 61 * 60 + 20)]);
    expect(html).toContain("No player positions for this match.");
    expect(html).toContain('class="pitch"');
  });

  it("colours and numbers sim players from the squads", () => {
    const who = whoFromSquads({
      home: [{ player_id: "h09", name: "Nine", shirt: 9 }],
      away: [{ player_id: "a04", name: "Four", shirt: 4 }],
    });
    expect(who("h09")).toEqual({ home: true, shirt: "9" });
    expect(who("a04")).toEqual({ home: false, shirt: "4" });
    const html = renderToStaticMarkup(<Pitch frame={tracked(61)} actions={[]} selected={null} label="x" who={who} />);
    expect(html.match(/class="pl"/g)).toHaveLength(3);            // two players and the ball
    expect(html).toContain("var(--pv-home)");
    expect(html).toContain("var(--pv-away)");
  });
});
