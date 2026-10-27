// Ax59: the match header shows the score with each team's scorers, and the viewer's controls
// (fan / analyst, ♥ team, ★ player) sit in it, not behind a Settings menu. Static HTML, no DOM.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import type { MatchEvent } from "@pivot/contracts";
import { PLAIN_PERIODS, minuteAt } from "../data/clock";
import { FixtureProvider } from "../data/match";
import { DEFAULT_PREFS, PrefsProvider } from "../i18n";
import { en } from "../i18n/messages/en";
import ScoreHeader, { scorers } from "./ScoreHeader";
import TopBar from "./TopBar";

const g = globalThis as { window?: { location: { search: string }; localStorage: Pick<Storage, "getItem" | "setItem" | "removeItem"> } };
const store = new Map<string, string>();
const withWindow = (search: string) => {
  g.window = { location: { search }, localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => void store.set(k, v), removeItem: (k) => void store.delete(k) } };
};
afterEach(() => {
  delete g.window;
  store.clear();
});

const render = () =>
  renderToStaticMarkup(
    <PrefsProvider>
      <MemoryRouter>
        <FixtureProvider>
          <TopBar prefs={DEFAULT_PREFS} onPrefsChange={() => {}} />
          <ScoreHeader prefs={DEFAULT_PREFS} onPrefsChange={() => {}} />
        </FixtureProvider>
      </MemoryRouter>
    </PrefsProvider>,
  );

const t = (key: string) => en[key as keyof typeof en] ?? key;
const goal = (team: "home" | "away", player_id: string, clock_label: string, t: number, play_pattern: MatchEvent["play_pattern"] = "open_play") =>
  ({ team, player_id, clock_label, t, type: "shot", shot_outcome: "goal", play_pattern }) as MatchEvent;

describe("the match header", () => {
  it("shows the score, the clock and who scored for each side", () => {
    withWindow("?from=90");
    const html = render();
    expect(html).toContain('aria-label="Harbour City 2, Northvale Rovers 1"');
    expect(html).toMatch(/aria-label="Harbour City goals"><li>Okafor 42′<\/li><li>Rossi 87′<\/li>/);
    expect(html).toMatch(/aria-label="Northvale Rovers goals"><li>Marsh 71′<\/li>/);
    expect(html).toContain("Full time");
  });

  it("puts fan / analyst, team and player in plain sight, with no Settings menu", () => {
    withWindow("");
    const html = render();
    const head = html.slice(html.indexOf('class="sh"'));
    expect(head).toContain('aria-label="Viewing mode"');
    expect(head).toContain(">Fan</button>");
    expect(head).toContain(">Analyst</button>");
    expect(head).toContain('aria-label="Your team"');
    expect(head).toContain('title="Player to follow"');
    expect(html).not.toContain("settings");
    // The match picker and the work log stay in the bar above.
    expect(html).toContain('class="btn top-trace"');
  });

  it("lists one line per scorer, goals in order, penalties marked", () => {
    const names: Record<string, string> = { a: "Ana Ruiz", b: "B. Okoro" };
    const events = [goal("home", "a", "77'", 77 * 60, "penalty"), goal("away", "b", "30'", 1800), goal("home", "a", "12'", 720)];
    expect(scorers(events, "home", (id) => names[id ?? ""] ?? "", t as never, (s) => minuteAt(PLAIN_PERIODS, s))).toEqual(["Ruiz 13′, 78′ (pen)"]);
    expect(scorers(events, "away", (id) => names[id ?? ""] ?? "", t as never, (s) => minuteAt(PLAIN_PERIODS, s))).toEqual(["Okoro 31′"]);
  });
});
