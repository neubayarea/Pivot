// Ax59: the match header shows the score with each team's scorers. Ax68: the viewer's controls
// (fan / analyst, ♥ team, ★ player) sit in the site bar above it, not behind a Settings menu.
// Static HTML, no DOM.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import type { MatchEvent } from "@pivot/contracts";
import { PLAIN_PERIODS, minuteAt } from "../data/clock";
import { FixtureProvider } from "../data/match";
import { DEFAULT_PREFS, PrefsProvider } from "../i18n";
import { en } from "../i18n/messages/en";
import type { FoldMode } from "../data/headerFold";
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

const render = (fold?: Parameters<typeof ScoreHeader>[0]["fold"], prefs = DEFAULT_PREFS) =>
  renderToStaticMarkup(
    <PrefsProvider>
      <MemoryRouter>
        <FixtureProvider>
          <TopBar prefs={DEFAULT_PREFS} onPrefsChange={() => {}} />
          <ScoreHeader prefs={prefs} fold={fold} />
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

  it("puts fan / analyst, team and player in the site bar next to the language, not in the header", () => {
    withWindow("");
    const html = render();
    const head = html.indexOf('class="mh"');
    const bar = html.slice(html.indexOf('class="top"'), head);
    expect(bar).toContain('class="top-view"');
    expect(bar).toContain('aria-label="Viewing mode"');
    expect(bar).toContain(">Fan</button>");
    expect(bar).toContain(">Analyst</button>");
    expect(bar).toContain('aria-label="Your team"');
    expect(bar).toContain('title="Player to follow"');
    // Right before the language switcher.
    expect(bar.indexOf('aria-label="Viewing mode"')).toBeLessThan(bar.indexOf('aria-label="Language"'));
    expect(html.slice(head)).not.toContain('aria-label="Viewing mode"');
    expect(html).not.toContain("settings");
    // The match picker and the work log stay in the bar too.
    expect(html).toContain('class="btn top-trace"');
  });

  it("has one View button for phones that says whether the panel is open", () => {
    withWindow("");
    const html = render();
    const id = html.match(/class="top-view-panel" role="group" aria-label="How you watch"/) && html.match(/<div id="([^"]+)" class="top-view-panel"/)?.[1];
    expect(id).toBeTruthy();
    expect(html).toContain(`<button type="button" class="btn top-view-btn" aria-expanded="false" aria-controls="${id}">View <span aria-hidden="true">▾</span></button>`);
  });

  it("lists one line per scorer, goals in order, penalties marked", () => {
    const names: Record<string, string> = { a: "Ana Ruiz", b: "B. Okoro" };
    const events = [goal("home", "a", "77'", 77 * 60, "penalty"), goal("away", "b", "30'", 1800), goal("home", "a", "12'", 720)];
    expect(scorers(events, "home", (id) => names[id ?? ""] ?? "", t as never, (s) => minuteAt(PLAIN_PERIODS, s))).toEqual(["Ruiz 13′, 78′ (pen)"]);
    expect(scorers(events, "away", (id) => names[id ?? ""] ?? "", t as never, (s) => minuteAt(PLAIN_PERIODS, s))).toEqual(["Okoro 31′"]);
  });
});

// Ax66: folded, the header is one slim bar of names, kit chips, score and clock.
describe("the folded header", () => {
  const noop = () => {};
  const fold = (mode: FoldMode, stuck = false) => ({ mode, stuck, expand: noop, collapse: noop });

  it("shows names, kit chips, the score and the clock", () => {
    withWindow("?from=90");
    const html = render(fold("slim"));
    const head = html.slice(html.indexOf('class="mh slim"'));
    expect(head).toContain('class="mh-bar"');
    expect(head.match(/class="mh-chip"/g)).toHaveLength(2);
    expect(head).toContain("Harbour City");
    expect(head).toContain("Northvale Rovers");
    expect(head).toContain('aria-label="Harbour City 2, Northvale Rovers 1"');
    expect(head).toContain("Full time");
    expect(head).not.toContain('class="mh-goals"');
  });

  it("has an expand button that says it is folded and what it opens", () => {
    withWindow("");
    const html = render(fold("slim"));
    expect(html).toMatch(/<button type="button" class="mh-toggle open" aria-expanded="false" aria-controls="[^"]+" aria-label="Expand the score header"/);
    expect(html).toContain('<span class="mh-toggle-txt">Expand</span>');
  });

  it("in full, has a collapse button", () => {
    withWindow("");
    const html = render(fold("auto"));
    expect(html).toContain('class="mh-toggle shut" aria-expanded="true"');
    expect(html).toContain('aria-label="Collapse the score header"');
  });

  it("leaves the controls in the site bar whether the header is slim or full", () => {
    withWindow("");
    for (const mode of ["slim", "auto", "full"] as const) {
      const html = render(fold(mode));
      expect(html.indexOf('aria-label="Viewing mode"')).toBeGreaterThan(-1);
      expect(html.indexOf('aria-label="Viewing mode"')).toBeLessThan(html.indexOf('aria-label="Match score"'));
    }
  });

  it("has no button where the page does not fold it", () => {
    withWindow("");
    expect(render()).not.toContain("mh-toggle");
  });

  it("marks the viewer's team in the slim bar too", () => {
    withWindow("");
    const html = render(fold("slim"), { ...DEFAULT_PREFS, focus_team: "away" });
    expect(html).toContain('class="mh-bar-team away fav"');
    expect(html).toContain('class="mh-bar-team home"');
  });

  // Ax77: the header scrolls away; the slim bar lies hidden over its bottom until it has.
  it("keeps the full header in the page and the slim bar hidden while the header is in view", () => {
    withWindow("");
    const html = render(fold("auto"));
    expect(html).toContain('class="mh" id=');
    expect(html).toContain('class="match-stick auto"');
    expect(html).toContain('class="mh slim off"');
  });

  it("shows the slim bar once the header has scrolled past", () => {
    withWindow("");
    const html = render(fold("auto", true));
    expect(html).toContain('class="mh slim"');
    expect(html).not.toContain("mh slim off");
  });

  it("pinned open, the whole header sticks and there is no slim bar", () => {
    withWindow("");
    const html = render(fold("full", true));
    expect(html).toContain('class="mh pinned"');
    expect(html).toContain('class="match-stick full"');
    expect(html).not.toContain("mh slim");
  });

  it("pinned folded, only the slim bar is left", () => {
    withWindow("");
    const html = render(fold("slim"));
    expect(html).not.toContain('class="mh-score"');
    expect(html).toContain('class="match-stick slim"><section class="mh slim" aria-label="Match score"');
  });
});
