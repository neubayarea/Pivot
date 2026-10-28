// Cx2: the interface and the explanations follow the chosen language; anything untranslated falls
// back to English; `?lang=` wins for recordings; a blocked localStorage changes nothing visible.
// Rendered to static HTML like states.test.tsx, so no DOM is needed.
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import WhyItTurned from "../components/WhyItTurned";
import { prefsQuery, withServedPrefs } from "../data/live/api";
import { FixtureProvider } from "../data/match";
import { LocalisingContext } from "../data/view";
import { DEMO_1021 } from "../fixtures/demo-1021";
import { localisePivot } from "../fixtures/demo-1021-i18n";
import LiveBoard from "../pages/LiveBoard";
import WhatIfLab from "../pages/WhatIfLab";
import {
  DEFAULT_PREFS, PrefsProvider, initialLang, needsLocalised, readSavedLang, saveLang, translator, type Lang,
} from "./index";
import { en } from "./messages/en";
import { es } from "./messages/es";
import { zh } from "./messages/zh";

type FakeWindow = { location: { search: string }; localStorage: Pick<Storage, "getItem" | "setItem"> };
const g = globalThis as { window?: FakeWindow };

function memoryStorage(): FakeWindow["localStorage"] {
  const m = new Map<string, string>();
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v) };
}
const blockedStorage: FakeWindow["localStorage"] = {
  getItem: () => {
    throw new DOMException("denied", "SecurityError");
  },
  setItem: () => {
    throw new DOMException("denied", "SecurityError");
  },
};

function withWindow(search: string, localStorage = memoryStorage()) {
  g.window = { location: { search }, localStorage };
  return g.window;
}

afterEach(() => {
  delete g.window;
  vi.restoreAllMocks();
});

const render = (node: ReactNode, path = "/") =>
  renderToStaticMarkup(
    <PrefsProvider>
      <MemoryRouter initialEntries={[path]}>{node}</MemoryRouter>
    </PrefsProvider>,
  );

const board = () => render(<FixtureProvider><LiveBoard /></FixtureProvider>, "/?tab=post&pivot=pv-74");
const pv74 = DEMO_1021.pivots.find((p) => p.pivot.pivot_id === "pv-74")!.pivot;

describe("switching language", () => {
  it("changes the interface and the demo explanation", () => {
    withWindow("?fixture=1&from=80&lang=en");
    const en = board();
    expect(en).toContain("Why it turned");
    expect(en).toContain("Back three steadied Harbour City");

    withWindow("?fixture=1&from=80&lang=zh");
    const zh = board();
    expect(zh).toContain("为什么会转折");
    expect(zh).toContain("改打三中卫，Harbour City 稳住阵脚");
    expect(zh).not.toContain("Why it turned");

    withWindow("?fixture=1&from=80&lang=es");
    const es = board();
    expect(es).toContain("Por qué cambió");
    expect(es).toContain("La línea de tres le dio aplomo a Harbour City");
  });

  it("keeps the checked figures highlighted in every language", () => {
    for (const lang of ["en", "zh", "es"] as const) {
      withWindow(`?lang=${lang}`);
      const html = render(<FixtureProvider><WhyItTurned pivot={localisePivot(pv74, lang)} selected={new Set()} onToggle={() => {}} /></FixtureProvider>);
      // "12 to 5" / "14 of 16" / "6 of 11" in each language's wording.
      expect(html.match(/class="src hl"/g)?.length, lang).toBe(3);
    }
  });

  it("translates the S3 notice", () => {
    withWindow("?lang=zh");
    expect(render(<FixtureProvider><Routes><Route path="/whatif/:id" element={<WhatIfLab />} /></Routes></FixtureProvider>, "/whatif/pv-74")).toContain("这是模拟，不是预测");
    withWindow("?lang=es");
    expect(render(<FixtureProvider><Routes><Route path="/whatif/:id" element={<WhatIfLab />} /></Routes></FixtureProvider>, "/whatif/pv-74")).toContain("Simulación, no una predicción");
  });

  it("says when the explanation came back in English", () => {
    withWindow("?lang=zh");
    const html = render(<FixtureProvider><WhyItTurned pivot={pv74} selected={new Set()} onToggle={() => {}} /></FixtureProvider>);
    expect(html).toContain("这个语言的解释暂未就绪");
    expect(html).not.toContain(pv74.narrative!.sentences[0].text);
    withWindow("?lang=en");
    expect(render(<FixtureProvider><WhyItTurned pivot={pv74} selected={new Set()} onToggle={() => {}} /></FixtureProvider>)).not.toContain("lang-note");
  });

  it("says the asked language is on its way while the API writes it (Ax31)", () => {
    withWindow("?lang=zh");
    const html = render(
      <FixtureProvider>
        <LocalisingContext.Provider value={true}>
          <WhyItTurned pivot={pv74} selected={new Set()} onToggle={() => {}} />
        </LocalisingContext.Provider>
      </FixtureProvider>,
    );
    expect(html).toContain("这个语言的解释暂未就绪");
    expect(html).not.toContain('lang="en"');
    expect(html).not.toContain(pv74.narrative!.sentences[0].text);
  });
});

describe("fan mode on the analyst version (Ax50)", () => {
  const why = (pivot: typeof pv74, localising = false) =>
    render(
      <FixtureProvider>
        <LocalisingContext.Provider value={localising}>
          <WhyItTurned pivot={pivot} selected={new Set()} onToggle={() => {}} />
        </LocalisingContext.Provider>
      </FixtureProvider>,
    );
  const asFan = (p: typeof pv74, language: Lang = "en") =>
    ({ ...p, narrative: { ...p.narrative!, prefs: { ...p.narrative!.prefs, audience: "fan", language } } }) as typeof pv74;

  it("says the fan version is being written, in every language", () => {
    withWindow("?mode=fan&lang=en");
    expect(why(pv74, true)).toContain("Writing the fan version. Showing the analyst version for now.");
    withWindow("?mode=fan&lang=zh");
    expect(why(localisePivot(pv74, "zh"), true)).toContain("正在写球迷版，先显示分析师版。");
    withWindow("?mode=fan&lang=es");
    expect(why(localisePivot(pv74, "es"), true)).toContain("Escribiendo la versión para aficionados.");
  });

  it("names both when the English analyst version stands in for a Chinese fan one", () => {
    withWindow("?mode=fan&lang=zh");
    expect(why(pv74, true)).toContain("这个语言的解释暂未就绪");
    expect(why(pv74)).toContain("这个语言的解释暂未就绪");
    expect(why(pv74)).not.toContain(pv74.narrative!.headline);
  });

  it("says nothing once the fan version is in, or for an analyst", () => {
    withWindow("?mode=fan&lang=zh");
    expect(why(asFan(localisePivot(pv74, "zh"), "zh"))).not.toContain("lang-note");
    withWindow("?mode=analyst&lang=en");
    expect(why(pv74, true)).not.toContain("lang-note");
  });
});

describe("missing translations", () => {
  it("fall back to English and warn once in dev", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const t = translator("zh", { en, zh: { "board.events": "比赛事件" }, es: {} });
    expect(t("board.events")).toBe("比赛事件");
    expect(t("board.pivots")).toBe("Turning points");
    expect(t("board.pivots")).toBe("Turning points");
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it("fill placeholders and leave unknown ones visible", () => {
    const t = translator("en");
    expect(t("board.pivotsNote", { n: 3 })).toBe("3 this match");
    expect(t("board.versus", { home: "HCY" })).toBe("HCY v {away}");
  });

  it.each([["zh", zh], ["es", es]] as const)("%s covers every English key", (_, table) => {
    expect(Object.keys(en).filter((k) => !(k in table))).toEqual([]);
  });
});

describe("choosing the language", () => {
  it("lets ?lang= beat the saved choice, which beats the browser", () => {
    expect(initialLang("?lang=zh", "es", ["en-US"])).toBe("zh");
    expect(initialLang("", "es", ["zh-CN"])).toBe("es");
    expect(initialLang("", null, ["fr-FR", "es-MX"])).toBe("es");
    expect(initialLang("", null, ["zh-Hant-TW"])).toBe("zh");
    expect(initialLang("?lang=fr", null, ["de"])).toBe("en");
  });

  it("remembers the choice in localStorage", () => {
    withWindow("");
    expect(readSavedLang()).toBeNull();
    saveLang("es");
    expect(readSavedLang()).toBe("es");
    expect(g.window!.localStorage.getItem("pivot.lang")).toBe("es");
  });

  it("ignores a junk saved value", () => {
    const w = withWindow("");
    w.localStorage.setItem("pivot.lang", "klingon");
    expect(readSavedLang()).toBeNull();
  });

  it("does not throw when localStorage is blocked", () => {
    withWindow("?fixture=1", blockedStorage);
    expect(readSavedLang()).toBeNull();
    expect(() => saveLang("zh")).not.toThrow();
    expect(() => board()).not.toThrow();
  });
});

describe("asking the API in the viewer's language", () => {
  it("sends lang and audience, and team and player only when set", () => {
    expect(prefsQuery(DEFAULT_PREFS)).toBe("?lang=en&audience=analyst");
    expect(prefsQuery({ audience: "fan", language: "zh", focus_team: "home", focus_player_id: "hcy-9" }))
      .toBe("?lang=zh&audience=fan&team=home&player=hcy-9");
  });

  it("reads the served language from the response prefs", () => {
    const served = { ...pv74, prefs: { ...DEFAULT_PREFS, language: "en" as Lang } };
    const pivot: Pivot = withServedPrefs(served);
    expect(pivot.narrative?.prefs.language).toBe("en");
    expect("prefs" in pivot).toBe(false);
  });

  it("only refetches pushed pivots when the viewer wants something other than English analyst", () => {
    expect(needsLocalised(DEFAULT_PREFS)).toBe(false);
    expect(needsLocalised({ ...DEFAULT_PREFS, language: "es" })).toBe(true);
    expect(needsLocalised({ ...DEFAULT_PREFS, audience: "fan" })).toBe(true);
  });
});
