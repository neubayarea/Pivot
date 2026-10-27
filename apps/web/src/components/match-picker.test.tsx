// Ax6: the viewer picks which match the board follows. `?match=` beats the saved pick; with neither,
// or one the server no longer has, the board opens the first match the API lists (Ax55: the first
// seed, not a match picked for how it went), and an old link says so. The picker lists the matches
// in the API's order and says when the server is still generating. Rendered to static HTML.
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Match } from "@pivot/contracts";
import { MatchChoiceContext, initialMatch, matchLabel, readSavedMatch, saveMatch } from "../data/choice";
import { pickMatch } from "../data/live/provider";
import { PrefsProvider, translator } from "../i18n";
import { MissingMatchBanner } from "./ConnectionBanner";
import { MatchPickerView } from "./MatchPicker";

type FakeStorage = Pick<Storage, "getItem" | "setItem">;
const g = globalThis as { window?: { location: { search: string }; localStorage: FakeStorage } };

function memoryStorage(): FakeStorage {
  const m = new Map<string, string>();
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v) };
}
const deny = () => {
  throw new DOMException("denied", "SecurityError");
};

function withWindow(search = "", localStorage: FakeStorage = memoryStorage()) {
  g.window = { location: { search }, localStorage };
}

afterEach(() => {
  delete g.window;
  vi.unstubAllGlobals();
});

const team = (short: string) => ({ short_name: short, name: short, squad: [] });
const match = (id: string, seed: number, status: Match["status"], home: number, away: number, preset: string | null = null) =>
  ({ match_id: id, seed, status, preset, score: { home, away }, home: team("HBC"), away: team("ROV") }) as unknown as Match;

// In the order GET /api/matches gives them: the simulated ones in seed-list order, then the others.
const MATCHES = [
  match("M-seed-101", 101, "finished", 4, 5),
  match("M-seed-212", 212, "finished", 3, 2),
  match("M-api-demo", 20261023, "live", 1, 2),
  match("M-seed-41", 41, "finished", 1, 0, "demo-1021"),
];

/** Answers the API from `matches`; any other match id is a 404. */
function stubApi(matches: Match[] = MATCHES) {
  const urls: string[] = [];
  vi.stubGlobal("fetch", async (url: string) => {
    urls.push(url);
    if (url === "/api/matches") return Response.json(matches);
    const hit = matches.find((m) => url === `/api/matches/${m.match_id}`);
    return hit ? Response.json(hit) : Response.json({ detail: "not found" }, { status: 404 });
  });
  return urls;
}

describe("which match is followed", () => {
  it("takes ?match= over the saved pick, and the saved pick otherwise", () => {
    expect(initialMatch("?match=M-seed-212", "M-seed-101")).toEqual({ id: "M-seed-212", fromUrl: true });
    expect(initialMatch("?lang=zh", "M-seed-101")).toEqual({ id: "M-seed-101", fromUrl: false });
    expect(initialMatch("", null)).toEqual({ id: null, fromUrl: false });
  });

  it("remembers the pick, and shrugs off blocked storage", () => {
    withWindow();
    saveMatch("M-seed-212");
    expect(readSavedMatch()).toBe("M-seed-212");
    withWindow("", { getItem: deny, setItem: deny });
    expect(() => saveMatch("M-seed-212")).not.toThrow();
    expect(readSavedMatch()).toBeNull();
  });

  it("opens the chosen match when the API has it", async () => {
    stubApi();
    expect(await pickMatch({ id: "M-seed-212", fromUrl: false })).toEqual({ id: "M-seed-212", missing: null });
    expect(await pickMatch({ id: "M-seed-41", fromUrl: true })).toEqual({ id: "M-seed-41", missing: null });
  });

  it("opens the first listed match when nothing is chosen, or a saved match is gone", async () => {
    stubApi();
    expect(await pickMatch()).toEqual({ id: "M-seed-101", missing: null });
    expect(await pickMatch({ id: "M-seed-999", fromUrl: false })).toEqual({ id: "M-seed-101", missing: null });
  });

  it("does not prefer a live match, a recorded demo or a result: the first in the list is the default", async () => {
    stubApi([MATCHES[1], MATCHES[3], MATCHES[2]]);
    expect((await pickMatch()).id).toBe("M-seed-212");
  });

  it("an old link to a match that is gone opens the default and reports the one asked for", async () => {
    stubApi();
    expect(await pickMatch({ id: "M-seed-29", fromUrl: true })).toEqual({ id: "M-seed-101", missing: "M-seed-29" });
  });

  it("has nothing to open on a server with no matches", async () => {
    stubApi([]);
    await expect(pickMatch({ id: "M-seed-29", fromUrl: true })).rejects.toThrow();
  });

  it("still fails on a server error instead of hiding it behind the default", async () => {
    vi.stubGlobal("fetch", async () => Response.json({ detail: "boom" }, { status: 500 }));
    await expect(pickMatch({ id: "M-seed-29", fromUrl: true })).rejects.toMatchObject({ status: 500 });
  });
});

describe("match picker", () => {
  const render = (generating: boolean) =>
    renderToStaticMarkup(
      <PrefsProvider>
        <MatchPickerView
          matches={MATCHES}
          sims={{ total: 6, ready: 2, failed: 0, generating, match_ids: [] }}
          value="M-seed-212"
          onChange={() => {}}
        />
      </PrefsProvider>,
    );

  it("labels each match with its score and seed, the recorded demo as the demo", () => {
    const t = translator("en");
    expect(matchLabel(MATCHES[0], t)).toBe("HBC 4–5 ROV · seed 101");
    expect(matchLabel(MATCHES[3], t)).toBe("HBC 1–0 ROV · demo");
    expect(matchLabel(MATCHES[2], t)).toBe("HBC 1–2 ROV · sample · Live");
    expect(matchLabel(MATCHES[0], translator("zh"))).toBe("HBC 4–5 ROV · 种子 101");
    expect(matchLabel(MATCHES[3], translator("zh"))).toBe("HBC 1–0 ROV · 演示");
  });

  it("lists every match in the API's order and selects the followed one", () => {
    withWindow("?lang=en");
    const html = render(false);
    expect([...html.matchAll(/<option value="([^"]+)"/g)].map((m) => m[1])).toEqual([
      "M-seed-101", "M-seed-212", "M-api-demo", "M-seed-41",
    ]);
    expect(html).toContain('<option value="M-seed-212" selected="">HBC 3–2 ROV · seed 212</option>');
    expect(html).not.toContain("Generating");
  });

  it("says so while the server is still generating, in the viewer's language", () => {
    withWindow("?lang=en");
    expect(render(true)).toContain("Generating matches… 2/6");
    withWindow("?lang=zh");
    expect(render(true)).toContain("正在生成比赛… 2/6");
    withWindow("?lang=es");
    expect(render(true)).toContain("Generando partidos… 2/6");
  });
});

describe("an old link to a match that is gone", () => {
  const render = (missing: string | null) =>
    renderToStaticMarkup(
      <PrefsProvider>
        <MatchChoiceContext.Provider
          value={{ choice: { id: missing, fromUrl: true }, choose: () => {}, missing, dismiss: () => {} }}
        >
          <MissingMatchBanner />
        </MatchChoiceContext.Provider>
      </PrefsProvider>,
    );

  it("says the asked-for match is gone and the first one is shown, in the viewer's language", () => {
    withWindow("?lang=en");
    expect(render("M-seed-29")).toContain("There is no match called “M-seed-29” any more, so the first match is shown instead.");
    withWindow("?lang=zh");
    expect(render("M-seed-29")).toContain("已经没有名为“M-seed-29”的比赛了");
  });

  it("says nothing when the link's match was there", () => {
    withWindow("?lang=en");
    expect(render(null)).toBe("");
  });
});
