// #315: the form in detail, rendered from a made-up `/prematch` answer in the shape of #314
// (fixtures/prematch-seed29.ts) on the recorded Harbour City v Rovers match: every block from the
// fixture, each block left out when its data is missing, the ♥ team's side marked, and fan mode.
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import type { Match } from "@pivot/contracts";
// a recorded match that never changes (eval/frozen/README.md)
import recorded from "../../../../eval/frozen/m-seed-29-before-ax44.json";
import { toView } from "../data/live/provider";
import { MatchContext } from "../data/match";
import { gameTags, type PreMatchReport, type TeamPreMatch } from "../data/prematch";
import { prematchSeed29 as fx } from "../fixtures/prematch-seed29";
import { PrefsProvider } from "../i18n";
import { PreMatchDeepView } from "./PreMatchDeep";

const g = globalThis as { window?: { location: { search: string }; localStorage: Pick<Storage, "getItem" | "setItem" | "removeItem"> } };

function withWindow(search: string) {
  const m = new Map<string, string>();
  g.window = { location: { search }, localStorage: { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v), removeItem: (k) => void m.delete(k) } };
}

afterEach(() => {
  delete g.window;
});

const view = toView({ match: recorded.match as unknown as Match, events: [], metrics: [], pivots: [] });
const html = (report: PreMatchReport) =>
  renderToStaticMarkup(
    <PrefsProvider>
      <MatchContext.Provider value={view}><PreMatchDeepView report={report} /></MatchContext.Provider>
    </PrefsProvider>,
  );
const text = (s: string) => s.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
const teams = (f: (t: TeamPreMatch) => TeamPreMatch): PreMatchReport => ({
  ...fx, teams: { home: f(fx.teams.home!), away: f(fx.teams.away!) },
});

describe("the form in detail", () => {
  it("shows the home and away record with today's split, and the results at this ground", () => {
    const out = text(html(fx));
    expect(out).toContain("Home and away record");
    for (const k of ["All games", "At home", "Away", "Today", "PPG"]) expect(out).toContain(k);
    // Harbour City at home 8 5 2 1 15 7 17 2.13, Rovers away 8 2 2 4 8 13 8 1.00.
    expect(out).toContain("At home Today 8 5 2 1 15 7 17 2.13");
    expect(out).toContain("Away Today 8 2 2 4 8 13 8 1.00");
    // Three meetings at Harbour Park, newest first, each with its half-time score.
    expect(out).toContain("At Harbour Park 3 meetings");
    expect(out).toContain("HBC won 2");
    expect(out).toContain("2025 HBC 3–0 ROV HT 2–0");
    expect(out.indexOf("2025 HBC 3–0")).toBeLessThan(out.indexOf("2023 HBC 1–1"));
    // Rovers' home games against Harbour City are not at this ground.
    expect(out).not.toContain("HBC 2–0 ROV");
  });

  it("lists the last five with half-time and full-time scores and marks comebacks, first goals and leads lost", () => {
    const out = text(html(fx));
    expect(out).toContain("Last five, with half-time scores");
    expect(out).toContain("Salt Harbour (home) HT 0–1 FT 2–1 Came from behind");
    expect(out).toContain("Westfield (home) HT 2–0 FT 2–2 Scored first Lead pegged back");
    expect(out.indexOf("Salt Harbour")).toBeLessThan(out.indexOf("Westfield (home)"));
    expect(gameTags(fx.teams.home!.last5[1])).toEqual(["first", "dropped"]);
  });

  it("puts the last five in numbers side by side, with the goals by period", () => {
    const out = text(html(fx));
    expect(out).toContain("Goals scored a game 1.6 1.4");
    expect(out).toContain("Clean sheets 1 of 5 2 of 5");
    expect(out).toContain("Over 2.5 goals 3 of 5 3 of 5");
    expect(out).toContain("Red cards 0 of 5 1 of 5");
    expect(out).toContain("Average rating 6.9 6.7");
    expect(out).toContain("HBC goals by period");
    expect(html(fx).match(/class="pre-pcol"/g)).toHaveLength(12);
  });

  it("says what each side plays next and how many regulars sit out, and that the simulation ignores it", () => {
    const out = text(html(fx));
    expect(out).toContain("Freeland Cup quarter-final");
    expect(out).toContain("Next: away to Eastmoor, in 3 days");
    expect(out).toContain("3 regular starters begin on the bench; 8 of the usual XI start.");
    for (const id of ["h12", "h13", "h14"]) expect(out).toContain(view.playerName(id));
    expect(out).toContain("Northgate Rovers start with their usual XI.");
    expect(out).toContain("the simulation does not take the next match into account");
    // A cup tie comes first, so the next league game is named too; the usual XI says how it was found.
    expect(out).toContain("Then in the league: Kingsbridge at home, in 7 days.");
    expect(out).toContain("started at least 3 of the last 5 league games");
    // The API's one-line caveat (about_key) closes the section, and stands in for the made-up note.
    expect(out).toContain("the half-time scores are estimated");
    expect(out).not.toContain("made up for this demo season");
    expect(text(html({ ...fx, about: null }))).toContain("made up for this demo season");
  });

  it("leaves out each block without its data, never showing zeros", () => {
    expect(html({ ...fx, teams: { home: null, away: null }, head_to_head: null })).toBe("");
    const empty = (r: TeamPreMatch["overall"]) => r && { ...r, played: 0, w: 0, d: 0, l: 0, gf: 0, ga: 0, pts: 0, ppg: 0 };
    const out = text(html({
      ...teams((t) => ({ ...t, overall: empty(t.overall), home_only: empty(t.home_only), away_only: empty(t.away_only), last5: [], next_fixture: null, usual_xi_today: null })),
      head_to_head: null,
    }));
    for (const absent of ["Home and away record", "Last five, with", "Next match", "0 of 5", "PPG", "At Harbour Park"]) expect(out).not.toContain(absent);
    // The stats with no value on either side drop out; one side missing shows a dash, not 0.
    const some = text(html(teams((t) => ({
      ...t, last5_stats: t.last5_stats && { ...t.last5_stats, reds: null, avg_rating: t === fx.teams.home ? 7.1 : null, goals_by_period: null, conceded_by_period: null },
    }))));
    expect(some).not.toContain("Red cards");
    expect(some).toContain("Average rating 7.1 –");
    expect(some).not.toContain("goals by period");
  });

  it("marks the ♥ team's side as yours and greys the other", () => {
    withWindow("?team=away");
    const out = html(fx);
    expect(text(out)).toContain("Your team");
    expect(text(out)).toContain("Opponent");
    expect(text(out)).toContain("seen from Northgate Rovers");
    expect(out).toContain('class="pre-col away mine"');
    expect(out).toContain('class="pre-col home theirs"');
    expect(out).toContain('class="pre-bar-val away mine"');
    delete g.window;
    const none = html(fx);
    expect(none).not.toContain("mine");
    expect(text(none)).not.toContain("Your team");
  });

  it("tells fans the story first in plain words, with four numbers and no tables", () => {
    withWindow("?mode=fan");
    const out = text(html(fx));
    expect(out.indexOf("What comes next")).toBeLessThan(out.indexOf("The last five games"));
    expect(out).toContain("Harbour City at home this season: won 5, drawn 2, lost 1.");
    expect(out).toContain("A big game soon, so they may rest players today.");
    expect(out).toContain("Kept a clean sheet");
    for (const absent of ["PPG", "Red cards", "Average rating", "goals by period", "Rotation risk"]) expect(out).not.toContain(absent);
  });

  it("speaks the page's language", () => {
    withWindow("?lang=zh");
    const out = text(html(fx));
    expect(out).toContain("主客场战绩");
    expect(out).toContain("半场 0–1 全场 2–1 逆转");
    expect(out).toContain("领先被追平");
    expect(out).toContain("Freeland Cup 1/4 决赛");
    expect(out).toContain("5 场 1 次");
    expect(out).toContain("半场比分是估算的");
    expect(out).not.toContain(" · ");
  });
});
