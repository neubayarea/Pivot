// C19 hotfix: a live match's /analysis?up_to=… has nulls wherever the match has not got to yet (blocks
// still to come, no shot yet, no share yet). Every part of the report draws it without throwing, shows
// "–" for the missing numbers, skips the blocks not reached, and a chart that does throw stays fenced in.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { PlayerReport } from "@pivot/contracts";
import { reached, type MatchAnalysis } from "../../data/analysis";
import { PrefsProvider } from "../../i18n";
import Deserved, { deservedVerdict } from "./Deserved";
import GameStateTable, { mostDangerous } from "./GameStateTable";
import Lanes, { laneShares } from "./Lanes";
import Phases, { bestSpell } from "./Phases";
import PlayerContrib, { topContributors } from "./PlayerContrib";
import ReportBoundary from "./ReportBoundary";
import ShotQuality from "./ShotQuality";
import StyleRadar from "./StyleRadar";
import { num, pct, share } from "./fmt";

const nulls = { xg: null, field_tilt_pct: null, possession_pct: null, ppda: null, shots: null };
const noState = { xg_per90: null, xga_per90: null, possession_pct: null, field_tilt_pct: null };
const noLane = { entries: null, xg: null };
/** Ten minutes into a live match: one block played, the next two not reached, nothing else known. */
const LIVE: MatchAnalysis = {
  deserved: { n_sims: 10000, home_win: null, draw: null, away_win: null, xpts: { home: null, away: null } },
  phases: [
    { from: 0, to: 15, home: { xg: 0.14, field_tilt_pct: 81.8, possession_pct: 56.2, ppda: 2.42, shots: 2 }, away: { xg: 0.27, field_tilt_pct: 18.2, possession_pct: 43.8, ppda: null, shots: 1 } },
    { from: 15, to: 30, home: nulls, away: nulls },
    { from: 30, to: 45, home: nulls, away: nulls },
  ],
  game_state: [{ state: "level", minutes: 10, home: noState, away: { ...noState, xg_per90: 2.43 } }, { state: "home_leading", minutes: null, home: noState, away: noState }],
  shot_quality: {
    home: { shots: 0, xg_per_shot: null, big_chances: null, by_source: { open_play: null, set_piece: null, penalty: null, counter: null } },
    away: { shots: 1, xg_per_shot: null, big_chances: 0, by_source: { open_play: 0.27, set_piece: null, penalty: null, counter: null } },
  },
  lanes: { home: { left: noLane, centre: noLane, right: noLane }, away: { left: noLane, centre: { entries: 2, xg: null }, right: noLane } },
  profile: { baseline_matches: 20, metrics: ["xg", "shots"], home: [null, 2.5], away: [null, null] },
};
const names = { home: "HBC", away: "ROV" };
const html = (node: React.ReactNode) => renderToStaticMarkup(<MemoryRouter><PrefsProvider>{node}</PrefsProvider></MemoryRouter>);

describe("the report on a live match's partial analysis", () => {
  it("formats null and NaN as a dash", () => {
    expect([num(null), num(Number.NaN), pct(undefined), share(null)]).toEqual(["–", "–", "–", "–"]);
    expect([num(0.1234), pct(55.6), share(0.49)]).toEqual(["0.12", "56%", "49%"]);
  });

  it("works out no sentence it has no numbers for", () => {
    expect(deservedVerdict(LIVE.deserved, { home: 0, away: 0 })).toBeNull();
    // Ten minutes is too short a state to say who was most dangerous in it (C21).
    expect(mostDangerous(LIVE.game_state)).toBeNull();
    expect(laneShares(LIVE.lanes.home)).toEqual({ left: 0, centre: 0, right: 0 });
    expect(topContributors([{ player_id: "p", name: "p", team: "home", shirt_number: 9, stats: { xg: null, xa: null, minutes_played: 10 } } as unknown as PlayerReport])).toEqual([]);
  });

  it("leaves out the blocks not reached yet", () => {
    const played = LIVE.phases.filter(reached);
    expect(played).toHaveLength(1);
    expect(bestSpell(played, "ppda")).toBeNull();
    expect(bestSpell(played, "xg")).toEqual({ i: 0, side: "away" });
  });

  it("draws every part without throwing", () => {
    expect(() => html(<Deserved d={LIVE.deserved} names={names} score={{ home: 0, away: 0 }} />)).not.toThrow();
    expect(html(<Deserved d={LIVE.deserved} names={names} score={{ home: 0, away: 0 }} />)).toContain("–");
    expect(() => html(<GameStateTable rows={LIVE.game_state} names={names} />)).not.toThrow();
    expect(() => html(<Phases phases={LIVE.phases.filter(reached)} names={names} marks={[]} />)).not.toThrow();
    expect(() => html(<ShotQuality shots={[]} quality={LIVE.shot_quality} names={names} nameOf={() => ""} />)).not.toThrow();
    expect(() => html(<Lanes lanes={LIVE.lanes} names={names} />)).not.toThrow();
    expect(() => html(<StyleRadar profile={LIVE.profile} names={names} />)).not.toThrow();
    expect(() => html(<PlayerContrib players={[]} short={names} />)).not.toThrow();
  });

  it("keeps a chart that throws inside the report, and tries again on new data", () => {
    // React runs these when a child throws (the browser, not a server render): the report shows its
    // own note, and a new key (the next minute of a live match) clears it.
    const failed = ReportBoundary.getDerivedStateFromError(new Error("chart failed"));
    expect(failed.error?.message).toBe("chart failed");
    expect(ReportBoundary.getDerivedStateFromProps({ children: null, resetKey: "m:660" }, { error: failed.error, key: "m:600" })).toEqual({ error: null, key: "m:660" });
    expect(ReportBoundary.getDerivedStateFromProps({ children: null, resetKey: "m:600" }, { error: failed.error, key: "m:600" })).toBeNull();
    expect(html(<ReportBoundary resetKey="m:600"><p>chart</p></ReportBoundary>)).toContain("chart");
  });
});
