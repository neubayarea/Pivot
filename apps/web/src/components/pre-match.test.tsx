// Ax60: the pre-match cards and the coach's plan, on a recorded match the API serves (form, table,
// head-to-head, news and ties all filled in), on a match with only the basics (what the simulated
// matches on the site send), and on a source with no pre-match data at all (the fixture).
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import type { Match } from "@pivot/contracts";
// a recorded match that never changes (eval/frozen/README.md)
import recorded from "../../../../eval/frozen/m-seed-29-before-ax44.json";
import { toView } from "../data/live/provider";
import { MatchContext, type MatchView } from "../data/match";
import { PrefsProvider } from "../i18n";
import { PreMatchTab } from "../pages/match/PreMatchTab";
import PreMatch from "./PreMatch";
import TeamTactics from "./TeamTactics";

const g = globalThis as { window?: { location: { search: string }; localStorage: Pick<Storage, "getItem" | "setItem" | "removeItem"> } };

function withWindow(search: string) {
  const m = new Map<string, string>();
  g.window = { location: { search }, localStorage: { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v), removeItem: (k) => void m.delete(k) } };
}

afterEach(() => {
  delete g.window;
});

const full = recorded.match as unknown as Match;
const viewOf = (match: Match) => toView({ match, events: [], metrics: [], pivots: [] });
const render = (view: MatchView, node: ReactNode) =>
  renderToStaticMarkup(
    <PrefsProvider>
      <MatchContext.Provider value={view}>{node}</MatchContext.Provider>
    </PrefsProvider>,
  );
const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

/** What a simulated match on the site sends before kick-off: the occasion, no season around it. */
const basic: Match = {
  ...full,
  context: { ...full.context, stakes: "none", form: [], head_to_head: null, news: [], relationships: [], effects: [], conditions: [] },
};

describe("the pre-match cards", () => {
  it("carry the context, coaches and tactics through toView", () => {
    const { preMatch } = viewOf(full);
    expect(preMatch?.context.form).toHaveLength(2);
    expect(preMatch?.plans.home.coach.name).toBe(full.home.coach.name);
    expect(preMatch?.plans.away.tactics).toEqual(full.away.tactics);
    expect(preMatch?.plans.home.club_id).toBe("club-hbc");
  });

  it("show form, table, head-to-head, news and ties from a recorded match", () => {
    const out = text(render(viewOf(full), <PreMatch />));
    // Harbour City 2nd on 57, Rovers 5th on 47; last five L L W W W, newest last.
    expect(out).toContain("2nd · 57 pts");
    expect(out).toContain("5th · 47 pts");
    expect(out).toContain("10 points apart");
    expect(out).toContain("L L W W W");
    expect(out).toContain("Last 5: 13 scored, 9 conceded");
    // 5 meetings: 2 each and a draw; newest first, the 2026 one won by Harbour City away.
    expect(out).toContain("5 meetings");
    expect(out).toContain("HBC won 2");
    expect(out).toContain("1 drawn");
    expect(out.indexOf("2026")).toBeLessThan(out.indexOf("2024"));
    expect(out).toContain("Title race");
    // News newest first, with whom it is about; a coach is named too.
    expect(out).toContain("Harbour City fans plan a hostile welcome");
    expect(out).toContain(`${full.away.coach.name} · Under fire`);
    // The ties: a04 back at his former club, and teammates now on opposite sides; not two current teammates.
    expect(out).toContain("away at former club Harbour City, left on bad terms");
    // h07, h09 and h14 with a04, h13 with a11; the ten pairs of current teammates are left out.
    expect(out.match(/Ex-teammates/g)).toHaveLength(4);
    // The routine per-player effects (form, big-match rating) stay out of the factors card.
    expect(out).toContain("Card risk ▲");
    expect(out).not.toContain("average rating");
  });

  it("show only the occasion when that is all the match has, never zeros", () => {
    const out = text(render(viewOf(basic), <PreMatch />));
    expect(out).toContain("Freeland League");
    expect(out).toContain("Harbour Park");
    expect(out).toContain("38,000");
    for (const absent of ["Form", "Head-to-head", "News", "Context effects", "Former clubs", "0 pts", "Last 0", "Title race"]) {
      expect(out).not.toContain(absent);
    }
  });

  it("render nothing without pre-match data (the fixture)", () => {
    const { preMatch: _, ...bare } = viewOf(full);
    expect(render(bare, <PreMatch />)).toBe("");
    expect(render(bare, <TeamTactics />)).toBe("");
  });

  it("use plain words in fan mode and drop the effect sizes", () => {
    withWindow("?mode=fan");
    const out = text(render(viewOf(full), <PreMatch />));
    expect(out).toContain("How they come in");
    expect(out).toContain("When they last met");
    expect(out).not.toMatch(/[+−]\d+\.\d%/);
  });

  it("speak the page's language", () => {
    withWindow("?lang=zh");
    const out = text(render(viewOf(full), <PreMatch />));
    expect(out).toContain("近期战绩与排名");
    expect(out).toContain("第 2 名");
  });
});

describe("the coach's plan", () => {
  it("puts both coaches, shapes and settings side by side", () => {
    const html = render(viewOf(full), <TeamTactics />);
    const out = text(html);
    expect(out).toContain(full.home.coach.name);
    expect(out).toContain(full.away.coach.name);
    expect(out).toContain(full.home.sheet.formation);
    expect(out).toContain(full.away.sheet.formation);
    for (const label of ["Pressing", "Defensive line", "Width", "Tempo", "Passing", "Attack focus"]) expect(out).toContain(label);
    // Both sides start on the defaults: the middle step of every meter.
    expect(html.match(/class="plan-val home"/g)).toHaveLength(6);
    expect(out).toContain("Corners: varied delivery, anywhere in the box, 5 players up");
    expect(out).toContain("Defending corners: mixed marking, 1 left up front");
  });

  it("shows a setting that differs, the switches that are on and the player instructions", () => {
    const tactics = {
      ...full.home.tactics, press: "high", line_height: "low", counter_attack: true,
      set_pieces: { ...full.home.tactics.set_pieces, corner_delivery: "inswing", corner_target: "near_post", corner_defence: "zonal" },
      instructions: [{ player_id: "h07", instruction: "man_mark", target_player_id: "a10" }],
    } as Match["home"]["tactics"];
    const view = viewOf({ ...full, home: { ...full.home, tactics } });
    const html = render(view, <TeamTactics />);
    const out = text(html);
    expect(out).toContain("High");
    expect(out).toContain("Deep");
    expect(out).toContain("Counter-attacks");
    expect(out).not.toContain("Offside trap");
    expect(out).toContain("inswinging, to the near post");
    expect(out).toContain("zonal marking");
    expect(out).toContain(`${view.playerName("h07")} man-marks ${view.playerName("a10")}`);
  });

  it("names the coach's usual shape when he starts in another", () => {
    const view = viewOf({ ...full, home: { ...full.home, coach: { ...full.home.coach, preferred_formation: "3-5-2" } } });
    expect(text(render(view, <TeamTactics />))).toContain("Usually 3-5-2");
  });
});

describe("the pre-match tab", () => {
  it("puts the build-up and the coach's plan in its slot, after the line-ups", () => {
    const html = render(viewOf(full), <PreMatchTab />);
    const slot = html.indexOf('data-slot="prematch"');
    expect(slot).toBeGreaterThan(html.indexOf("Line-ups"));
    expect(html.indexOf("Form &amp; table")).toBeGreaterThan(slot);
    expect(html.indexOf("The coach&#x27;s plan")).toBeGreaterThan(slot);
  });
});
