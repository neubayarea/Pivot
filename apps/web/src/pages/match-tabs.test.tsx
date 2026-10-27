// C13 (#316): the match page is six tabs by content, each with its own link (`?tab=`), opening where
// the match is; old Ax59 links (`?tab=pre|live|post`) still land. Static HTML on the fixture, no DOM.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import WhyItTurned from "../components/WhyItTurned";
import { FixtureProvider } from "../data/match";
import { defaultTab, tabFrom, tabSearch } from "../data/tab";
import { DEMO_1021 } from "../fixtures/demo-1021";
import { PrefsProvider } from "../i18n";
import LiveBoard from "./LiveBoard";

const g = globalThis as { window?: { location: { search: string }; localStorage: Pick<Storage, "getItem" | "setItem" | "removeItem"> } };
const store = new Map<string, string>();
const withWindow = (search: string) => {
  g.window = { location: { search }, localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => void store.set(k, v), removeItem: (k) => void store.delete(k) } };
};
afterEach(() => {
  delete g.window;
  store.clear();
});

const board = (path: string) => {
  withWindow(`${path.slice(path.indexOf("?"))}&from=90`);
  return renderToStaticMarkup(
    <PrefsProvider>
      <MemoryRouter initialEntries={[path]}>
        <FixtureProvider><LiveBoard /></FixtureProvider>
      </MemoryRouter>
    </PrefsProvider>,
  );
};
const selected = (html: string) => html.match(/id="tab-(\w+)" role="tab" aria-selected="true"/)?.[1];

describe("tab links", () => {
  it("opens where the match is when the link names no tab", () => {
    expect(defaultTab("scheduled")).toBe("preview");
    expect(defaultTab("live")).toBe("replay");
    expect(defaultTab("paused")).toBe("replay");
    expect(defaultTab("finished")).toBe("overview");
    expect(tabFrom("", "finished")).toBe("overview");
    expect(tabFrom("?tab=nonsense", "scheduled")).toBe("preview");
    expect(tabFrom("?match=M-seed-101&tab=stats", "finished")).toBe("stats");
  });

  it("sends old links to the tab that holds the same things now", () => {
    expect(tabFrom("?tab=pre", "finished")).toBe("preview");
    expect(tabFrom("?tab=live", "finished")).toBe("replay");
    expect(tabFrom("?tab=post", "live")).toBe("overview");
  });

  it("keeps the match, the replay and the viewer settings when switching", () => {
    expect(tabSearch("?match=M-seed-101&from=0&mode=fan", "overview")).toBe("?match=M-seed-101&from=0&mode=fan&tab=overview");
    expect(tabSearch("?tab=pre&match=m1", "whatif")).toBe("?tab=whatif&match=m1");
  });

  it("renders the six tabs as links in content order, the open one selected", () => {
    const html = board("/?match=demo-1021&tab=stats");
    expect(selected(html)).toBe("stats");
    const labels = ["Overview", "What if", "Live|Replay", "Stats", "Line-ups", "Preview"]
      .map((l) => html.search(new RegExp(`>(${l})</a>`)));
    expect(labels.every((i) => i > 0)).toBe(true);
    expect([...labels].sort((a, b) => a - b)).toEqual(labels);
    expect(html).toContain('href="/?match=demo-1021&amp;tab=whatif"');
    expect(html).toContain('role="tabpanel" id="panel-stats" aria-labelledby="tab-stats"');
    expect(selected(board("/?tab=post"))).toBe("overview");
    expect(selected(board("/?tab=pre"))).toBe("preview");
  });
});

describe("what each tab holds", () => {
  it("replay: the pitch, key stats, events and line-ups, no analysis and no full stats table", () => {
    const html = board("/?tab=replay");
    for (const part of ["On the pitch", "Match stats", "Events", "Line-ups"]) expect(html).toContain(part);
    expect(html).not.toContain("Why it turned");
    expect(html).not.toContain("Key moments");
    expect(html).not.toContain("Shots, heat and passing");
  });

  it("stats: the team stats and the match pictures", () => {
    const html = board("/?tab=stats");
    expect(html).toContain("Team stats");
    expect(html).toContain("Shots, heat and passing");
    expect(html).not.toContain("On the pitch");
  });

  it("overview: the turning points and their explanation", () => {
    const html = board("/?tab=overview");
    expect(html).toContain("Back three steadied Harbour City");
    expect(html).toContain("Key moments");
    expect(board("/?tab=overview&pivot=pv-74")).toContain("Why it turned");
  });

  it("what-if: the lab for the first turning point, each turning point a chip", () => {
    const html = board("/?tab=whatif");
    expect(html).toContain('class="wi-tab"');
    expect(html).toMatch(/class="chip" aria-pressed="true"/);
  });

  it("line-ups: both XIs; preview: says so when the match has no pre-match data (the fixture has none)", () => {
    const lu = board("/?tab=lineups");
    expect(lu).toContain("Line-ups");
    expect(lu).toContain("Harbour City");
    const pre = board("/?tab=preview");
    expect(pre).not.toContain('data-slot="prematch"');
    expect(pre).toContain("No pre-match information for this match.");
    expect(pre).not.toContain("On the pitch");
  });
});

describe("evidence numbers in the explanation", () => {
  const pv74 = DEMO_1021.pivots.find((p) => p.pivot.pivot_id === "pv-74")!.pivot;
  const why = (search: string) => {
    withWindow(search);
    return renderToStaticMarkup(
      <PrefsProvider><MemoryRouter><FixtureProvider><WhyItTurned pivot={pv74} selected={new Set()} onToggle={() => {}} /></FixtureProvider></MemoryRouter></PrefsProvider>,
    );
  };

  it("analysts see them, fans get one tap per sentence instead", () => {
    const analyst = why("?mode=analyst");
    expect(analyst).toMatch(/class="ev"[^>]*>#\d+/);
    expect(analyst).not.toContain("ev-more");
    const fan = why("?mode=fan");
    expect(fan).not.toMatch(/class="ev"[^>]*>#\d+/);
    expect(fan).toMatch(/class="ev-more" aria-expanded="false">Sources \(\d+\)/);
  });
});
