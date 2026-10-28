import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it } from "vitest";
import type { MatchEvent, Pivot1, StatMetricInfo } from "@pivot/contracts";
import { FixtureProvider, type MatchView } from "../data/match";
import { PrefsProvider, translator } from "../i18n";
import { describe } from "./EventFeed";
import { pivotHeadline } from "./PivotList";
import { statText } from "./TeamStats";
import WhyItTurned from "./WhyItTurned";

const teams = { home: { name: "Tessmouth United" }, away: { name: "Vantry Town" } } as MatchView["teams"];
const pivot = {
  pivot_id: "p12", minute: 12, direction: "away", status: "confirmed",
  narrative: { headline: "Vantry Town take control", prefs: { language: "en", audience: "analyst" }, sentences: [
    { text: "English explanation", claims: [], evidence_ids: [] },
  ] },
} as unknown as Pivot1;

afterEach(() => { delete (globalThis as { window?: unknown }).window; });

it("uses a localized momentum summary for a foreign-language headline, but keeps a matching headline", () => {
  expect(pivotHeadline(pivot, teams, translator("en"))).toBe("Vantry Town take control");
  expect(pivotHeadline(pivot, teams, translator("zh"))).toBe("场面倒向 Vantry Town");
  expect(pivotHeadline(pivot, teams, translator("es"))).not.toContain("take control");
});

it("does not display English explanation text under a Chinese heading", () => {
  (globalThis as { window?: unknown }).window = {
    location: { search: "?lang=zh" }, localStorage: { getItem: () => null },
  };
  const html = renderToStaticMarkup(<PrefsProvider><MemoryRouter><FixtureProvider>
    <WhyItTurned pivot={pivot} selected={new Set()} onToggle={() => {}} />
  </FixtureProvider></MemoryRouter></PrefsProvider>);
  expect(html).toContain("这个语言的解释暂未就绪");
  expect(html).not.toContain("English explanation");
});

it("preserves PPDA precision instead of displaying two different ratios as the same integer", () => {
  const metric = { unit: "ratio", metric: "ppda" } as StatMetricInfo;
  expect(statText(5.8, metric)).toBe("5.8");
  expect(statText(5.6, metric)).toBe("5.6");
  expect(statText(null, metric)).toBe("–");
});

it("omits the empty side suffix for a corner whose side is unknown", () => {
  const corner = { type: "pass", pass_type: "corner", meta: {}, player_id: null } as unknown as MatchEvent;
  expect(describe(corner, () => "", translator("zh"))).toBe("角球");
  expect(describe(corner, () => "", translator("en"))).toBe("Corner");
});
