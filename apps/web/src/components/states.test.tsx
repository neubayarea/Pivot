// C06: the loading, empty, error and degraded states render the words the viewer needs. Rendered
// to static HTML so the tests need no DOM.
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { classifyLoadError } from "../data/live/provider";
import { ApiError } from "../data/live/api";
import { startDemo, replayUrl, REPLAY_URL } from "../data/demo";
import { MatchContext, computeStats, isRedCard, type Connection, type MatchView } from "../data/match";
import LiveBoard from "../pages/LiveBoard";
import PivotDetail from "../pages/PivotDetail";
import { ErrorScreen } from "./ErrorBoundary";
import EventFeed from "./EventFeed";
import PivotList from "./PivotList";
import Playback from "./Playback";
import { Startup } from "./StartupScreen";

const narrative = {
  chain_id: null, headline: "Substitution flipped the left flank", verifier_attempts: 1, source: "llm",
  prefs: { audience: "analyst", language: "en", focus_team: null, focus_player_id: null },
  sentences: [{ text: "The left flank opened up.", claims: [], evidence_ids: [] }],
} as unknown as Pivot["narrative"];

const pivot = (minute: number, status: Pivot["status"]): Pivot => ({
  pivot_id: `p${minute}`, match_id: "m1", chain_id: "c", minute, status, direction: "away", severity: 3,
  trigger_event_ids: [], narrative: status === "pending" ? null : narrative,
});

function matchView(over: Partial<MatchView> = {}, status: MatchView["match"]["status"] = "live"): MatchView {
  const team = (side: "home" | "away", name: string) => ({ name, short_name: name.slice(0, 3).toUpperCase(), side, color: "#000" });
  const pivots = over.pivots ?? [];
  return {
    match: {
      match_id: "m1", clock: status === "scheduled" ? 0 : 3000, period: 1, status, speed: 1, clockLabel: "50:00",
      score: { home: 0, away: 0, home_penalties: null, away_penalties: null },
    },
    teams: { home: team("home", "Northvale"), away: team("away", "Eastport") },
    events: [], metrics: [], pivots, stats: computeStats([]),
    squads: { home: [], away: [] }, playerName: (id) => id ?? "", eventById: () => undefined,
    pivotDetail: (id) => {
      const p = pivots.find((x) => x.pivot_id === id);
      return p && { pivot: p, window: [0, 60], frames: [{ match_id: "m1", period: 1, t: 0, possession: null, players: [], ball: { owner_id: null, x: 0, y: 0, z: 0 } }], beforeAfter: [] };
    },
    playback: null,
    ...over,
  };
}

const render = (node: ReactNode, view?: MatchView, path = "/") =>
  renderToStaticMarkup(
    <MemoryRouter initialEntries={[path]}>
      {view ? <MatchContext.Provider value={view}>{node}</MatchContext.Provider> : node}
    </MemoryRouter>,
  );

const conn = (over: Partial<Connection>): Connection =>
  ({ state: "reconnecting", attempt: 2, problem: null, retryNow: () => {}, ...over });

describe("startup screen", () => {
  it("shows card outlines, not a spinner, while connecting", () => {
    const html = render(<Startup conn={conn({ state: "connecting", attempt: 0 })} />);
    expect(html).toContain("sk-card");
    expect(html).toContain("Loading the live match");
  });

  it("offers Start demo when the API has no matches", () => {
    const html = render(<Startup conn={conn({ problem: { kind: "no-matches" } })} />);
    expect(html).toContain("No matches yet");
    expect(html).toContain("Start demo match");
  });

  it("explains an unknown match and links back", () => {
    const html = render(<Startup conn={conn({ problem: { kind: "not-found", matchId: "M-x" } })} />);
    expect(html).toContain("Match not found");
    expect(html).toContain("M-x");
    expect(html).toContain("Open the latest match");
  });

  it("offers retry and the replay when the server is down", () => {
    const html = render(<Startup conn={conn({ problem: { kind: "unreachable" } })} />);
    expect(html).toContain("reach the Pivot server");
    expect(html).toContain("Retry now");
    expect(html).toContain(`href="${REPLAY_URL.replace("&", "&amp;")}"`);
    expect(html).toContain("attempt 2");
  });
});

describe("load errors", () => {
  it("sorts failures into what the viewer can do about them", () => {
    expect(classifyLoadError(new ApiError(404, ""), "M-x")).toEqual({ kind: "not-found", matchId: "M-x" });
    expect(classifyLoadError(new ApiError(502, ""), null)).toEqual({ kind: "unreachable" });
    expect(classifyLoadError(new ApiError(500, ""), null)).toEqual({ kind: "server", status: 500 });
    expect(classifyLoadError(new ApiError(500, "", false), null)).toEqual({ kind: "unreachable" });
    expect(classifyLoadError(new TypeError("Failed to fetch"), null)).toEqual({ kind: "unreachable" });
  });

  it("replays the chosen match, or the fixture when there is none to name", () => {
    (globalThis as { window?: unknown }).window = { location: { search: "" } };
    const went: string[] = [];
    try {
      startDemo("M-seed-505", (u) => went.push(u));
      startDemo(undefined, (u) => went.push(u));
    } finally {
      delete (globalThis as { window?: unknown }).window;
    }
    expect(went).toEqual([replayUrl("M-seed-505"), REPLAY_URL]);
    expect(replayUrl("M-seed-505")).toBe("/?match=M-seed-505&from=0");
  });
});

describe("live board states", () => {
  it("shows kick-off pending with a Start match button", () => {
    const html = render(<LiveBoard />, matchView({}, "scheduled"));
    expect(html).toContain("Kick-off pending");
    expect(html).toContain("Start match");
    expect(html).toContain("No pivots yet");
    expect(html).toContain("No events yet");
  });

  it("offers Start demo once a live match is over", () => {
    expect(render(<LiveBoard />, matchView({}, "finished"))).toContain("Start demo");
    expect(render(<LiveBoard />, matchView({}, "live"))).not.toContain("Start demo");
  });

  it("shows the cream banner and Auto summary stamp for a degraded pivot", () => {
    const html = render(<LiveBoard />, matchView({ pivots: [pivot(63, "degraded")] }));
    expect(html).toContain("AI explanations delayed. Showing automatic summaries.");
    expect(html).toContain('stamp warn">Auto summary');
    expect(html).not.toContain("Verified ✓");
  });

  it("keeps verified pivots verified and drops rejected ones", () => {
    const html = render(<PivotList activeId={null} />, matchView({ pivots: [pivot(70, "rejected"), pivot(63, "confirmed")] }));
    expect(html).toContain("Verified ✓");
    expect(html).not.toContain("70′");
  });

  it("has a pitch board once the match has started", () => {
    const html = render(<LiveBoard />, matchView());
    expect(html).toContain("On the pitch");
    expect(html).toContain("No player positions for this match.");
    expect(render(<LiveBoard />, matchView({}, "scheduled"))).not.toContain("On the pitch");
  });

  it("gives each part of More details its own grid cell, the line-ups apart from the pitch", () => {
    const html = render(<LiveBoard />, matchView());
    // styles/base.css places these cells by name: pitch and stats on top, events and line-ups under, the AI's work below.
    const cells = [...html.matchAll(/class="card [^"]*\bmore-(\w+)/g)].map((m) => m[1]);
    expect(cells.sort()).toEqual(["events", "pitch", "roster", "stats", "trace"]);
    expect(html).toContain("Line-ups");
  });

  it("puts one timeline over the whole replay, and none on the live feed", () => {
    const playback = { playing: true, setPlaying: () => {}, setSpeed: () => {}, restart: () => {}, seek: () => {}, end: 5700 };
    const html = render(<Playback />, matchView({ playback, pivots: [pivot(63, "confirmed")] }));
    expect(html).toContain('type="range"');
    expect(html).toContain('max="5700"');
    expect(html).toContain("64′");                 // elapsed minute 63 is the 64th minute on the clock
    expect(html).toContain("Restart");
    expect(render(<Playback />, matchView())).toBe("");
  });

  it("says when the event feed is empty", () => {
    expect(render(<EventFeed highlight={new Set()} />, matchView())).toContain("No events yet");
  });

  it("reads a red card from foul.card, as the simulator sends it, or the fixture's meta.card", () => {
    const card = (card: "yellow" | "second_yellow" | "red") => ({ type: "card" as const, meta: {},
      foul: { foul_type: "tackle" as const, advantage_played: false, penalty_awarded: false, card, card_reason: null } });
    expect([card("red"), card("second_yellow"), card("yellow")].map(isRedCard)).toEqual([true, true, false]);
    expect(isRedCard({ type: "card", foul: null, meta: { card: "red" } })).toBe(true);
  });
});

describe("pivot detail and crashes", () => {
  it("explains a missing pivot instead of a blank page", () => {
    const html = render(<PivotDetail />, matchView(), "/pivot/nope");
    expect(html).toContain("Pivot not found");
    expect(html).toContain("Back to the live board");
  });

  it("the error boundary screen offers a way back", () => {
    const html = render(<ErrorScreen error={new Error("boom")} />);
    expect(html).toContain("Something went wrong");
    expect(html).toContain("Reload the page");
    expect(html).toContain("boom");
  });
});
