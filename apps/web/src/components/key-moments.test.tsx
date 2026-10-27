// Ax38: the key moments (goals, red cards, penalties, VAR reversals) and what a goal did to the
// score; the board's words for a match that never turned. Events copied from M-seed-404 (2–2,
// levelled in stoppage time, no pivot on the live site) and M-seed-29 (the demo match).
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { MatchEvent, Pivot1 as Pivot } from "@pivot/contracts";
import { keyMoments, linkedPivot, matchPhase } from "../data/keyMoments";
import { MatchContext, computeStats, type MatchView } from "../data/match";
import LiveBoard from "../pages/LiveBoard";

type Ev = Partial<MatchEvent> & Pick<MatchEvent, "event_id" | "period" | "period_t" | "t" | "type" | "team">;
const ev = (e: Ev): MatchEvent => ({
  seq: Number(e.event_id.slice(-5)) || 0, shot_outcome: null, play_pattern: "open_play", meta: {}, foul: null, var: null,
  player_id: `${e.team}-9`, location: null, clock_label: "", minute: Math.floor(e.t / 60), ...e,
} as MatchEvent);
const H1 = 0, H2 = 2946;     // second half kicks off after five minutes of first-half stoppage
const goal = (id: string, team: "home" | "away", period_t: number, clock_label: string, extra: Partial<MatchEvent> = {}) =>
  ev({ event_id: id, type: "shot", shot_outcome: "goal", team, period: 2, period_t, t: H2 + period_t, clock_label, ...extra });

// M-seed-404: four second-half goals, the last two in stoppage time.
const SEED_404 = [
  ev({ event_id: "m004-s00050", type: "card", team: "home", period: 1, period_t: 225, t: H1 + 225, clock_label: "4'", foul: { card: "yellow" } as MatchEvent["foul"] }),
  goal("m077-s01400", "away", 1685, "74'"),
  goal("m081-s01504", "home", 2039, "79'"),
  ev({ event_id: "m081-s01505", type: "var_review", team: "home", period: 2, period_t: 2039, t: H2 + 2039, clock_label: "79'",
    var: { review_of: "goal", reviewed_event_id: "m081-s01504", decision: "confirmed", reason: "handball", duration_s: 97 } }),
  ev({ event_id: "m095-s01700", type: "foul", team: "away", period: 2, period_t: 2759, t: H2 + 2759, clock_label: "90+1'",
    foul: { card: null, penalty_awarded: true } as unknown as MatchEvent["foul"] }),
  goal("m096-s01720", "home", 2824, "90+3'"),
  goal("m103-s01900", "away", 3208, "90+9'"),
  ev({ event_id: "m103-s01910", type: "period_end", team: "home", period: 2, period_t: 3214, t: H2 + 3214, clock_label: "90+9'" }),
];

// M-seed-29: 3–1 with a red card at 38′, a penalty VAR took back at 46′ and a goal from the ten men late on.
const SEED_29 = [
  goal("m010-s00222", "home", 0, "11'", { period: 1, period_t: 645, t: 645 }),
  ev({ event_id: "m037-s00678", type: "card", team: "away", period: 1, period_t: 2220, t: 2220, clock_label: "38'", foul: { card: "red" } as MatchEvent["foul"] }),
  goal("m039-s00714", "home", 0, "40'", { period: 1, period_t: 2391, t: 2391 }),
  ev({ event_id: "m049-s00879", type: "foul", team: "home", period: 2, period_t: 26, t: 2972, clock_label: "46'",
    foul: { card: null, penalty_awarded: true } as unknown as MatchEvent["foul"] }),
  ev({ event_id: "m049-s00880", type: "var_review", team: "away", period: 2, period_t: 26, t: 2972, clock_label: "46'",
    var: { review_of: "penalty", reviewed_event_id: "m049-s00879", decision: "overturned", reason: "no_foul", duration_s: 88 } }),
  goal("m055-s00963", "home", 376, "52'"),
  goal("m089-s01553", "away", 2448, "86'"),
];

const team = (side: "home" | "away", name: string, short: string) => ({ name, short_name: short, side, color: "#000" });
const pivot = (minute: number, trigger_event_ids: string[] = []): Pivot => ({
  pivot_id: `p${minute}`, match_id: "m1", chain_id: "c", minute, status: "confirmed", direction: "away", severity: 2, trigger_event_ids,
  narrative: { chain_id: null, headline: "Momentum swings", verifier_attempts: 1, source: "template",
    prefs: { audience: "analyst", language: "en", focus_team: null, focus_player_id: null }, sentences: [] } as unknown as Pivot["narrative"],
});

function view(events: MatchEvent[], status: MatchView["match"]["status"], pivots: Pivot[] = []): MatchView {
  const newest = [...events].sort((a, b) => b.t - a.t || b.seq - a.seq);
  return {
    match: { match_id: "m1", clock: newest[0]?.t ?? 0, period: 2, status, speed: 1, clockLabel: "", score: { home: 2, away: 2, home_penalties: null, away_penalties: null } },
    teams: { home: team("home", "Harbour City", "HBC"), away: team("away", "Northgate Rovers", "ROV") },
    events: newest, metrics: [{ match_id: "m1", minute: 1, momentum: 0.2, threat_home: 0, threat_away: 0, pressure_home: 0, pressure_away: 0 }],
    pivots, stats: computeStats([]), squads: { home: [], away: [] }, playerName: (id) => id ?? "",
    eventById: (id) => events.find((e) => e.event_id === id),
    pivotDetail: (id) => {
      const p = pivots.find((x) => x.pivot_id === id);
      return p && { pivot: p, window: [(p.minute - 5) * 60, (p.minute + 5) * 60], frames: [{ match_id: "m1", period: 1, t: 0, possession: null, players: [], ball: { owner_id: null, x: 0, y: 0, z: 0 } }], beforeAfter: [] };
    },
    playback: null,
  };
}
const render = (v: MatchView) =>
  renderToStaticMarkup(<MemoryRouter initialEntries={["/?tab=post"]}><MatchContext.Provider value={v}><LiveBoard /></MatchContext.Provider></MemoryRouter>);

describe("key moments", () => {
  it("M-seed-404: tells the opener, the equaliser, the comeback and the stoppage-time equaliser apart", () => {
    const keys = keyMoments(SEED_404, true);
    expect(keys.map((k) => [k.event.clock_label, k.kind, k.side, k.situation, k.score && `${k.score.home}-${k.score.away}`])).toEqual([
      ["74'", "goal", "away", "opener", "0-1"],
      ["79'", "goal", "home", "equaliser", "1-1"],
      ["90+1'", "penalty", "home", undefined, undefined],
      ["90+3'", "goal", "home", "comeback", "2-1"],
      ["90+9'", "goal", "away", "stoppageEqualiser", "2-2"],
    ]);
  });

  it("M-seed-29: red card, a penalty VAR took back, goals that extend the lead and one pulled back", () => {
    const keys = keyMoments(SEED_29, true);
    expect(keys.map((k) => [k.event.clock_label, k.kind, k.side, k.situation])).toEqual([
      ["11'", "goal", "home", "opener"],
      ["38'", "red", "away", undefined],
      ["40'", "goal", "home", "extend"],
      ["46'", "penalty", "away", undefined],
      ["46'", "var", "away", undefined],
      ["52'", "goal", "home", "extend"],
      ["86'", "goal", "away", "pullBack"],
    ]);
    // The pivots at 39′ and 89′: the red card and the 40′ goal set off the first, the 86′ goal the last.
    const pivots = [{ minute: 39, trigger_event_ids: ["m037-s00678", "m039-s00714"] }, { minute: 69, trigger_event_ids: [] }, { minute: 89, trigger_event_ids: ["m089-s01553"] }];
    expect(keys.map((k) => linkedPivot(k, pivots))).toEqual([0, 1, 1, 0, 0, 0, 3]);
  });

  it("a late go-ahead goal is the winner only once the match is over and nobody answered", () => {
    const events = [goal("a", "home", 600, "56'"), goal("b", "away", 2500, "87'"), goal("c", "home", 2800, "90+2'")];
    expect(keyMoments(events, true).at(-1)?.situation).toBe("winner");
    expect(keyMoments(events, false).at(-1)?.situation).toBe("lead");
  });

  it("an own goal counts for the other side, a goal VAR ruled out and shoot-out kicks do not count", () => {
    const events = [
      ev({ event_id: "og", type: "clearance", team: "home", period: 1, period_t: 300, t: 300, meta: { own_goal: "true" } }),
      goal("ruled-out", "home", 400, "52'", { shot_outcome: "disallowed" }),
      goal("pen", "home", 500, "54'", { play_pattern: "penalty" }),
      goal("shootout", "away", 10, "PEN", { period: 5 }),
    ];
    expect(keyMoments(events, true).map((k) => [k.side, k.ownGoal, k.penalty, k.situation])).toEqual([
      ["away", true, false, "opener"],
      ["home", false, true, "equaliser"],
    ]);
  });

  it("knows half-time from the last period boundary", () => {
    const end1 = ev({ event_id: "e1", type: "period_end", team: "home", period: 1, period_t: 2830, t: 2830 });
    const ko2 = ev({ event_id: "k2", type: "kickoff", team: "away", period: 2, period_t: 0, t: 2946 });
    expect(matchPhase("live", [end1])).toBe("halfTime");
    expect(matchPhase("live", [ko2, end1])).toBe("live");
    expect(matchPhase("finished", [ko2, end1])).toBe("finished");
  });
});

describe("board without pivots", () => {
  it("a finished match that never turned says so and leads with its key moments", () => {
    const html = render(view(SEED_404, "finished"));
    // C11: the score is in the header band; the page no longer repeats it in a kicker.
    expect(html).not.toContain("Full time: Harbour City 2–2 Northgate Rovers");
    expect(html).toContain("No clear swing in momentum in this match");
    expect(html).not.toContain("Watching for the first pivot");
    expect(html).not.toContain("No pivots yet");
    expect(html).not.toContain("Kick-off");
    expect(html).toContain("Key moments");
    expect(html).toContain("Stoppage-time equaliser");
    expect(html).toContain("Turns it round");
    expect(html).toContain("Penalty to HBC");
    // Key moments come right after the momentum line, before set pieces and shots.
    expect(html.indexOf("Momentum")).toBeLessThan(html.indexOf("Key moments"));
    expect(html.indexOf("Key moments")).toBeLessThan(html.indexOf("Set pieces &amp; shots"));
    // Four goals and a penalty marked on the line, and a legend for them; no numbered pivot in it.
    expect(html.match(/class="mom-key/g)).toHaveLength(5);
    expect(html).toContain("km-legend");
    expect(html).not.toContain("Pivot: the run of play turned");
  });

  it("a match still going says it is watching, under the right phase", () => {
    const live = SEED_404.filter((e) => e.t < H2 + 2000);
    const html = render(view(live, "live"));
    expect(html).toContain("Kick-off: Harbour City");
    expect(html).toContain("Watching for the first pivot");
    expect(html).toContain("No pivots yet. Watching the momentum line.");
    expect(html).not.toContain("No clear swing");
    const ht = render(view([ev({ event_id: "e1", type: "period_end", team: "home", period: 1, period_t: 2830, t: 2830 })], "live"));
    expect(ht).toContain("Half-time: Harbour City");
  });

  it("M-seed-29 keeps its numbered pivots first and links the key moments to them", () => {
    const html = render(view(SEED_29, "finished", [pivot(39, ["m037-s00678", "m039-s00714"]), pivot(69), pivot(89, ["m089-s01553"])]));
    expect(html).toContain("The 3 moments that changed the course of this match");
    expect(html).not.toContain("No clear swing");
    expect(html).toContain(">Pivot ①<");
    expect(html).toContain(">Pivot ③<");
    expect(html).toContain("VAR overturns it: no penalty");
    expect(html).toContain("Pivot: the run of play turned");
    expect(html.indexOf("mc to-")).toBeLessThan(html.indexOf("Key moments"));
  });
});
