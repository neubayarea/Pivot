// Ax59: the match page is three tabs, each with its own link (`?tab=pre|live|post`), the live one
// by default; the open pivot is in the link too. Static HTML on the fixture, no DOM.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import WhyItTurned from "../components/WhyItTurned";
import { FixtureProvider } from "../data/match";
import { DEFAULT_TAB, tabFrom, tabSearch } from "../data/tab";
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
  it("reads the tab from the link, live when it is missing or unknown", () => {
    expect(DEFAULT_TAB).toBe("live");
    expect(tabFrom("")).toBe("live");
    expect(tabFrom("?match=M-seed-101&tab=pre")).toBe("pre");
    expect(tabFrom("?tab=post")).toBe("post");
    expect(tabFrom("?tab=stats")).toBe("live");
  });

  it("keeps the match, the replay and the viewer settings when switching", () => {
    expect(tabSearch("?match=M-seed-101&from=0&mode=fan", "post")).toBe("?match=M-seed-101&from=0&mode=fan&tab=post");
    expect(tabSearch("?tab=pre&match=m1", "live")).toBe("?tab=live&match=m1");
  });

  it("renders the three tabs as links, the open one selected", () => {
    const html = board("/?match=demo-1021");
    expect(selected(html)).toBe("live");
    expect(html).toContain('href="/?match=demo-1021&amp;tab=pre"');
    expect(html).toContain('href="/?match=demo-1021&amp;tab=post"');
    expect(html).toContain(">Pre-match</a>");
    expect(html).toContain(">Live</a>");
    expect(html).toContain(">Post-match</a>");
    expect(html).toContain('role="tabpanel" id="panel-live" aria-labelledby="tab-live"');
    expect(selected(board("/?tab=post"))).toBe("post");
    expect(selected(board("/?tab=pre"))).toBe("pre");
  });
});

describe("what each tab holds", () => {
  it("live: the pitch, stats, events and line-ups, no analysis", () => {
    const html = board("/?tab=live");
    for (const part of ["On the pitch", "Match stats", "Events", "Line-ups"]) expect(html).toContain(part);
    expect(html).not.toContain("Why it turned");
    expect(html).not.toContain("Key moments");
  });

  it("post: six numbered sections in order, the pivots one line each until one is opened", () => {
    const html = board("/?tab=post");
    const order = ["Pivots", "Momentum", "Key moments", "Set pieces &amp; shots", "What if…", "AI work log"]
      .map((h) => html.indexOf(`-hd">${h}</h2>`));
    expect(order.every((i) => i > 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    expect(html).toContain("Back three steadied Harbour City");
    expect(html).not.toContain("Why it turned");
    expect(html).not.toContain("More details");
    const opened = board("/?tab=post&pivot=pv-74");
    expect(opened).toContain("Why it turned");
    expect(opened).toContain('aria-pressed="true"');
  });

  it("pre: the line-ups and a marked slot for the pre-match content", () => {
    const html = board("/?tab=pre");
    expect(html).toContain("Line-ups");
    expect(html).toContain("Harbour City");
    expect(html).toContain('data-slot="prematch"');
    expect(html).not.toContain("On the pitch");
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
