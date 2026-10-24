// C08: viewing mode, team and player change what the API is asked for and what the page marks;
// the choices survive a reload, `?mode=&team=&player=` wins for recordings, and a blocked
// localStorage changes nothing visible. Rendered to static HTML like i18n.test.tsx, so no DOM.
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ViewerPrefs } from "@pivot/contracts";
import { ApiError, api } from "../data/live/api";
import { listPivotsFor } from "../data/live/provider";
import { FixtureProvider } from "../data/match";
import { DEMO_1021 } from "../fixtures/demo-1021";
import { DEFAULT_PREFS, PrefsProvider, initialView, readSavedView, saveView, usePrefs } from "../i18n";
import LiveBoard from "../pages/LiveBoard";
import PivotDetail from "../pages/PivotDetail";
import TopBar from "./TopBar";
import WhyItTurned, { nameMatcher } from "./WhyItTurned";

type FakeStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;
type FakeWindow = { location: { search: string }; localStorage: FakeStorage };
const g = globalThis as { window?: FakeWindow };

function memoryStorage(): FakeStorage {
  const m = new Map<string, string>();
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v), removeItem: (k) => void m.delete(k) };
}
const deny = () => {
  throw new DOMException("denied", "SecurityError");
};
const blockedStorage: FakeStorage = { getItem: deny, setItem: deny, removeItem: deny };

function withWindow(search: string, localStorage = memoryStorage()) {
  g.window = { location: { search }, localStorage };
  return g.window;
}

// Node has a real navigator with the machine's language; these tests expect English unless they ask.
beforeEach(() => {
  vi.stubGlobal("navigator", { language: "en-US", languages: ["en-US"] });
});

afterEach(() => {
  delete g.window;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const render = (node: ReactNode, path = "/") =>
  renderToStaticMarkup(
    <PrefsProvider>
      <MemoryRouter initialEntries={[path]}>
        <FixtureProvider>{node}</FixtureProvider>
      </MemoryRouter>
    </PrefsProvider>,
  );

/** Prints what PrefsProvider started with, i.e. what a freshly loaded page would use. */
function Probe() {
  const { prefs } = usePrefs();
  return <>{`${prefs.audience}|${prefs.focus_team}|${prefs.focus_player_id}`}</>;
}
const started = () => renderToStaticMarkup(<PrefsProvider><Probe /></PrefsProvider>);

/** Records the URLs the API client asks for. */
function stubFetch(answer: (url: string) => Response = () => Response.json([])) {
  const urls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    urls.push(url);
    return answer(url);
  }));
  return urls;
}
const query = (url: string) => Object.fromEntries(new URL(url, "http://x").searchParams);

const pv38 = DEMO_1021.pivots.find((p) => p.pivot.pivot_id === "pv-38")!.pivot;

describe("asking for the explanation", () => {
  it("sends the mode, team and player after each switch", async () => {
    const urls = stubFetch();
    let prefs: ViewerPrefs = DEFAULT_PREFS;
    await api.listPivots("m1", prefs);
    prefs = { ...prefs, audience: "fan" };
    await api.listPivots("m1", prefs);
    prefs = { ...prefs, focus_team: "away" };
    await api.listPivots("m1", prefs);
    prefs = { ...prefs, focus_player_id: "nvr-10" };
    await api.listPivots("m1", prefs);
    prefs = { ...prefs, focus_team: null, focus_player_id: null, audience: "analyst" };
    await api.listPivots("m1", prefs);

    expect(urls.map(query)).toEqual([
      { lang: "en", audience: "analyst" },
      { lang: "en", audience: "fan" },
      { lang: "en", audience: "fan", team: "away" },
      { lang: "en", audience: "fan", team: "away", player: "nvr-10" },
      { lang: "en", audience: "analyst" },
    ]);
  });

  it("asks for one pushed pivot with the same settings", async () => {
    const urls = stubFetch(() => Response.json(pv38));
    await api.getPivot("pv-38", { audience: "fan", language: "es", focus_team: "home", focus_player_id: "hcy-9" });
    expect(urls[0]).toMatch(/^\/api\/pivots\/pv-38\?/);
    expect(query(urls[0])).toEqual({ lang: "es", audience: "fan", team: "home", player: "hcy-9" });
  });

  it("drops a player the API does not know instead of failing the load", async () => {
    const urls = stubFetch((url) =>
      query(url).player ? Response.json({ detail: "unknown player" }, { status: 422 }) : Response.json([pv38]));
    const pivots = await listPivotsFor("m1", { ...DEFAULT_PREFS, focus_player_id: "someone-else" });
    expect(pivots).toHaveLength(1);
    expect(urls.map((u) => query(u).player ?? null)).toEqual(["someone-else", null]);
  });

  it("still reports other API errors", async () => {
    stubFetch(() => Response.json({}, { status: 500 }));
    await expect(listPivotsFor("m1", { ...DEFAULT_PREFS, focus_player_id: "hcy-9" })).rejects.toBeInstanceOf(ApiError);
  });
});

describe("remembering the settings", () => {
  it("restores mode, team and player after a reload", () => {
    withWindow("");
    expect(started()).toBe("analyst|null|null");
    saveView({ audience: "fan", focus_team: "away", focus_player_id: "nvr-10" });
    // A reload: a new provider reads what the last one saved.
    expect(started()).toBe("fan|away|nvr-10");
    saveView({ audience: "analyst", focus_team: null, focus_player_id: null });
    expect(started()).toBe("analyst|null|null");
    expect(g.window!.localStorage.getItem("pivot.team")).toBeNull();
  });

  it("lets ?mode=&team=&player= beat the saved choice", () => {
    const saved = { audience: "analyst", focus_team: "away", focus_player_id: "nvr-10" } as const;
    expect(initialView("?mode=fan&team=home&player=hcy-11", saved))
      .toEqual({ audience: "fan", focus_team: "home", focus_player_id: "hcy-11" });
    expect(initialView("", saved)).toEqual(saved);
    expect(initialView("?team=none&player=none", saved)).toEqual({ ...saved, focus_team: null, focus_player_id: null });
    expect(initialView("?mode=pundit&team=left", {})).toEqual({ audience: "analyst", focus_team: null, focus_player_id: null });
  });

  it("ignores junk in storage", () => {
    const w = withWindow("");
    w.localStorage.setItem("pivot.mode", "pundit");
    w.localStorage.setItem("pivot.team", "left");
    expect(readSavedView()).toEqual({});
  });

  it("does not throw when localStorage is blocked", () => {
    withWindow("?fixture=1&mode=fan", blockedStorage);
    expect(readSavedView()).toEqual({});
    expect(() => saveView({ audience: "fan", focus_team: "home", focus_player_id: null })).not.toThrow();
    expect(started()).toBe("fan|null|null");
    expect(() => render(<LiveBoard />)).not.toThrow();
  });
});

describe("what the page shows", () => {
  it("names the stats in plain words in fan mode", () => {
    withWindow("?from=80");
    expect(render(<LiveBoard />)).toContain("Final-third passes");
    withWindow("?from=80&mode=fan");
    const fan = render(<LiveBoard />);
    expect(fan).toContain("Balls into the danger zone");
    expect(fan).not.toContain("Final-third passes");
    withWindow("?from=80&mode=fan&lang=zh");
    expect(render(<LiveBoard />)).toContain("打到危险区域的球");
  });

  it("marks the viewer's team in the top bar and the stats", () => {
    withWindow("?from=80&team=away");
    const html = render(<><TopBar prefs={{ ...DEFAULT_PREFS, focus_team: "away" }} onPrefsChange={() => {}} /><LiveBoard /></>);
    expect(html).toMatch(/class="tm fav"><span class="tm-full">Northvale Rovers/);
    expect(html).toContain('class="r fav"');
  });

  it("puts the followed player in the picker", () => {
    withWindow("");
    const html = render(<TopBar prefs={{ ...DEFAULT_PREFS, focus_player_id: "hcy-11" }} onPrefsChange={() => {}} />);
    expect(html).toContain("Moreau");
    expect(html).toContain("Player: A. Moreau");
  });

  it("highlights the followed player's name and his evidence in the explanation", () => {
    withWindow("?player=hcy-9");
    const html = render(<WhyItTurned pivot={pv38} selected={new Set()} onToggle={() => {}} />);
    expect(html).toContain('<span class="hl who">Okafor</span>');
    expect(html).toMatch(/class="ev star"[^>]*>★ #/);
    withWindow("");
    expect(render(<WhyItTurned pivot={pv38} selected={new Set()} onToggle={() => {}} />)).not.toContain("hl who");
  });

  it("outlines the followed player on the S2 pitch", () => {
    withWindow("?player=hcy-9");
    const html = render(<Routes><Route path="/pivot/:id" element={<PivotDetail />} /></Routes>, "/pivot/pv-38");
    expect(html).toContain('class="pl followed"');
    expect(html).toContain("Gold ring: D. Okafor");
    withWindow("");
    expect(render(<Routes><Route path="/pivot/:id" element={<PivotDetail />} /></Routes>, "/pivot/pv-38")).not.toContain("followed");
  });

  it("matches names as whole words only", () => {
    const re = nameMatcher("A. Moreau")!;
    expect("A. Moreau went off".split(re)).toEqual(["", "A. Moreau", " went off"]);
    expect("Moreau's run".split(re)[1]).toBe("Moreau");
    expect("Moreauville".split(re)).toHaveLength(1);
    expect(nameMatcher("")).toBeNull();
  });
});
