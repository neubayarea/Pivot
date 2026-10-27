// #315: the form in detail, rendered from the real `/prematch` answer for M-seed-101 (#327, saved
// in fixtures/prematch-m-seed-101.json) on the recorded Harbour City v Rovers match (same clubs and
// ground): every block, each block left out when its data is missing, the ♥ team's side marked, and
// fan mode. The cup tie, the rested regulars and a lead given away do not happen in that match, so
// those tests change the real answer.
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import type { Match } from "@pivot/contracts";
// a recorded match that never changes (eval/frozen/README.md)
import recorded from "../../../../eval/frozen/m-seed-29-before-ax44.json";
import { toView } from "../data/live/provider";
import { MatchContext } from "../data/match";
import { gameTags, type PrematchReport, type PrematchTeam } from "../data/prematch";
import real from "../fixtures/prematch-m-seed-101.json";
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

const fx = real as unknown as PrematchReport;
const view = toView({ match: recorded.match as unknown as Match, events: [], metrics: [], pivots: [] });
const html = (report: PrematchReport) =>
  renderToStaticMarkup(
    <PrefsProvider>
      <MatchContext.Provider value={view}>
        <PreMatchDeepView report={report} />
      </MatchContext.Provider>
    </PrefsProvider>,
  );
const text = (s: string) => s.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
const teams = (f: (t: PrematchTeam, side: "home" | "away") => PrematchTeam): PrematchReport => ({
  ...fx, teams: { home: f(fx.teams.home, "home"), away: f(fx.teams.away, "away") },
});
/** Harbour City with a cup quarter-final in 3 days and three regulars rested; the league game after it. */
const cup = teams((t, side) => side === "away" ? t : {
  ...t,
  next_fixture: {
    ...t.next_fixture!, competition: "Freeland Cup", stage: "Quarter-final", matchday: null, opponent: "Eastmoor", opponent_id: "club-eas",
    days_until: 3, importance: "high", rotation_risk: "high", fictional: true,
  },
  usual_xi_today: { ...t.usual_xi_today, regulars_starting: 8, regulars_benched: ["h09", "h10", "h11"], newcomers: ["h12", "h13", "h14"] },
});

describe("the form in detail", () => {
  it("shows the home and away record with today's split, and the results at this ground", () => {
    const out = text(html(fx));
    expect(out).toContain("Home and away record");
    for (const k of ["All games", "At home", "Away", "Today", "PPG"]) expect(out).toContain(k);
    // Harbour City at home 12 6 3 3 22 16 21 1.75; Rovers away 18 9 5 4 31 22 32 1.78.
    expect(out).toContain("At home Today 12 6 3 3 22 16 21 1.75");
    expect(out).toContain("Away Today 18 9 5 4 31 22 32 1.78");
    // Two meetings at Harbour Park, newest first, each with its half-time score; not Rovers' home games.
    expect(out).toContain("At Harbour Park 2 meetings");
    expect(out).toContain("HBC won 1");
    expect(out).toContain("2025 HBC 2–2 ROV HT 1–2");
    expect(out).toContain("2024 HBC 3–2 ROV HT 2–0");
    expect(out.indexOf("2025 HBC 2–2")).toBeLessThan(out.indexOf("2024 HBC 3–2"));
    expect(out).not.toContain("2026 HBC");
  });

  it("lists the last five, newest first, with half-time and full-time scores and their marks", () => {
    const out = text(html(fx));
    expect(out).toContain("Last five, with half-time scores");
    expect(out).toContain("Vantry Town (away) HT 1–1 FT 1–2");
    expect(out).toContain("Ostrin Albion (home) HT 3–1 FT 4–1 Scored first");
    expect(out).toContain("Fallowden (away) HT 0–1 FT 1–1 Came back to draw");
    expect(gameTags({ ...fx.teams.home.last5[4], ft: [2, 1], result: "W" })).toEqual(["comeback"]);
    expect(out.indexOf("Vantry Town")).toBeLessThan(out.indexOf("Ostrin Albion"));
    // A half-time lead that was not kept is marked; there is none in the real match.
    expect(out).not.toContain("Lead pegged back");
    const dropped = { ...fx.teams.home.last5[0], ht: [1, 0] as [number, number], scored_first: true };
    expect(gameTags(dropped)).toEqual(["first", "dropped"]);
    expect(text(html(teams((t) => ({ ...t, last5: [dropped, ...t.last5.slice(1)] }))))).toContain("Scored first Lead pegged back");
  });

  it("puts the last five in numbers side by side, with the goals by period", () => {
    const out = text(html(fx));
    expect(out).toContain("Goals scored a game 1.2 2.8");
    expect(out).toContain("Goals conceded a game 1.8 1.0");
    expect(out).toContain("Clean sheets 0 of 5 3 of 5");
    expect(out).toContain("Over 2.5 goals 3 of 5 4 of 5");
    expect(out).toContain("Red cards 2 of 5 0 of 5");
    expect(out).toContain("Average rating 6.5 6.7");
    expect(out).toContain("HBC goals by period");
    expect(html(fx).match(/class="pre-pcol"/g)).toHaveLength(12);
  });

  it("says what each side plays next, that the usual XI starts, and that the simulation ignores it", () => {
    const out = text(html(fx));
    expect(out).toContain("Freeland League");
    expect(out).toContain("Next: away to Tessmouth United, in 7 days");
    expect(out).toContain("Next: Vantry Town at home, in 7 days");
    expect(out).toContain("Harbour City start with their usual XI.");
    expect(out).toContain("started at least 3 of the last 5 league games");
    expect(out).toContain("the simulation does not take the next match into account");
    // The API's one-line caveat (about_key) closes the section.
    expect(out).toContain("the half-time scores are estimated");
  });

  it("names a cup tie, the league game after it and the regulars rested for it", () => {
    const out = text(html(cup));
    expect(out).toContain("Freeland Cup quarter-final");
    expect(out).toContain("Next: away to Eastmoor, in 3 days");
    expect(out).toContain("Then in the league: away to Tessmouth United, in 7 days.");
    expect(out).toContain("3 regular starters begin on the bench; 8 of the usual XI start.");
    for (const id of ["h09", "h10", "h11", "h12"]) expect(out).toContain(view.playerName(id));
    // With the API's caveat there the page does not add its own made-up note; without it, it does.
    expect(out).not.toContain("made up for this demo season");
    expect(text(html({ ...cup, about: "" }))).toContain("made up for this demo season");
  });

  it("leaves out each block without its data, never showing zeros", () => {
    const none = { ...fx, teams: {}, head_to_head: null } as unknown as PrematchReport;
    expect(html(none)).toBe("");
    const empty = (r: PrematchTeam["overall"]) => ({ ...r, played: 0, w: 0, d: 0, l: 0, gf: 0, ga: 0, pts: 0, ppg: 0 });
    const bare = {
      ...teams((t) => ({ ...t, overall: empty(t.overall), home_only: empty(t.home_only), away_only: empty(t.away_only), last5: [], next_fixture: null, next_league: null, usual_xi_today: null }) as unknown as PrematchTeam),
      head_to_head: null,
    } as unknown as PrematchReport;
    const out = text(html(bare));
    for (const absent of ["Home and away record", "Last five, with", "Next match", "0 of 5", "PPG", "At Harbour Park"]) expect(out).not.toContain(absent);
    // A stat with no value on either side drops out; one side missing shows a dash, not 0.
    const some = text(html(teams((t, side) => ({
      ...t, last5_stats: { ...t.last5_stats, reds: null, avg_rating: side === "home" ? 7.1 : null, goals_by_period: null, conceded_by_period: null },
    }) as unknown as PrematchTeam)));
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
    const out = text(html(cup));
    expect(out.indexOf("What comes next")).toBeLessThan(out.indexOf("The last five games"));
    expect(out).toContain("Harbour City at home this season: won 6, drawn 3, lost 3.");
    expect(out).toContain("A big game soon, so they may rest players today.");
    expect(out).toContain("Kept a clean sheet");
    for (const absent of ["PPG", "Red cards", "Average rating", "goals by period", "Rotation risk", "Then in the league"]) expect(out).not.toContain(absent);
  });

  it("speaks the page's language", () => {
    withWindow("?lang=zh");
    const out = text(html(cup));
    expect(out).toContain("主客场战绩");
    expect(out).toContain("半场 3–1 全场 4–1 先进球");
    expect(out).toContain("半场 0–1 全场 1–1 落后扳平");
    expect(out).toContain("Freeland Cup 1/4 决赛");
    expect(out).toContain("5 场 3 次");
    expect(out).toContain("半场比分是估算的");
    expect(out).not.toContain(" · ");
  });
});
