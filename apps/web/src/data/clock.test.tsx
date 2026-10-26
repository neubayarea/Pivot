// G2 / Ax27: every minute on the page reads the match clock, the one the event list uses, so a
// pivot, its chips and the event that caused it name the same minute however long the stoppage.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { MatchEvent, Pivot1 as Pivot } from "@pivot/contracts";
import MomentumChart from "../components/MomentumChart";
import PivotList from "../components/PivotList";
import { ScenarioChips } from "../components/WhatIf";
import { translator } from "../i18n";
import { PLAIN_PERIODS, clockAt, eventMinute, minuteAt, minuteLabel, type PeriodStart } from "./clock";
import { computeStats, MatchContext, type MatchView } from "./match";
import { optionLabel, type ScenarioOption } from "./scenarios";

// Three minutes of first-half stoppage: the second half kicks off 48 minutes in.
const PERIODS: PeriodStart[] = [{ period: 1, start_t: 0 }, { period: 2, start_t: 48 * 60 }];

describe("match clock", () => {
  it("labels elapsed time like a broadcast, the same as pivot_core's label_at", () => {
    expect([0, 39, 44, 45, 47, 48, 69, 101].map((m) => minuteLabel(PERIODS, m)))
      .toEqual(["1", "40", "45", "45+1", "45+3", "46", "67", "90+9"]);
    expect(minuteAt([...PERIODS, { period: 5, start_t: 7000 }], 7100)).toBe("PEN");
    expect(minuteLabel(PLAIN_PERIODS, 63)).toBe("64");          // no stoppage: elapsed + 1
  });

  it("runs the top-bar clock from 45:00 at the second-half kick-off", () => {
    expect(clockAt(PERIODS, 46 * 60 + 30)).toBe("46:30");      // first-half stoppage runs on
    expect(clockAt(PERIODS, 48 * 60 + 5)).toBe("45:05");
    expect(clockAt(PERIODS, 69 * 60)).toBe("66:00");
  });

  it("reads an event's own clock label", () => {
    expect(eventMinute({ clock_label: "45+2'" })).toBe("45+2");
  });
});

const SUB = {
  event_id: "sub", seq: 9, t: 48 * 60 + 17 * 60 + 40, minute: 65, period: 2, period_t: 17 * 60 + 40,
  clock_label: "63'", team: "home", type: "substitution", meta: {}, shot_outcome: null,
} as unknown as MatchEvent;

const pivot: Pivot = {
  pivot_id: "p69", match_id: "m1", chain_id: "c", minute: 69, status: "confirmed", direction: "away", severity: 3,
  trigger_event_ids: ["sub"],
  narrative: { chain_id: null, headline: "The substitution turned it", verifier_attempts: 1, source: "llm",
    prefs: { audience: "analyst", language: "en", focus_team: null, focus_player_id: null },
    sentences: [{ text: "x", claims: [], evidence_ids: ["sub"], context_ids: [] }] },
} as Pivot;

function view(): MatchView {
  const team = (side: "home" | "away", name: string) => ({ name, short_name: name.slice(0, 3).toUpperCase(), side, color: "#000" });
  return {
    match: { match_id: "m1", clock: 75 * 60, period: 2, status: "live", speed: 1, clockLabel: "72:00", periods: PERIODS,
      score: { home: 1, away: 1, home_penalties: null, away_penalties: null } },
    teams: { home: team("home", "Harbour"), away: team("away", "Rovers") },
    events: [SUB], metrics: [], pivots: [pivot], stats: computeStats([]), squads: { home: [], away: [] },
    playerName: (id) => id ?? "", eventById: (id) => (id === "sub" ? SUB : undefined),
    pivotDetail: () => undefined, playback: null,
  };
}

const render = (node: React.ReactNode) => renderToStaticMarkup(
  <MemoryRouter><MatchContext.Provider value={view()}>{node}</MatchContext.Provider></MemoryRouter>,
);

describe("one minute everywhere (M-seed-29's 69 pivot)", () => {
  const cancel: ScenarioOption = {
    type: "cancel_substitution", label: "Cancel 63′ substitution", enabled: true, disabled_reason: null,
    target_event_id: "sub", at_minute: 65, team: "home", params: {},
  };
  const press: ScenarioOption = {
    type: "change_press", label: "Press higher from 67′", enabled: true, disabled_reason: null,
    target_event_id: null, at_minute: 69, team: "home", params: {},
  };

  it("the pivot list, the chart flag and the chips agree with the event list", () => {
    expect(render(<PivotList activeId={null} />)).toContain('<span class="m">67′</span>');
    const chart = render(<MomentumChart metrics={[]} pivots={[pivot]} homeLabel="Harbour" awayLabel="Rovers" />);
    expect(chart).toContain("67′");
    expect(chart).not.toContain("69′");
    const chips = render(<ScenarioChips options={[cancel, press]} selected={null} onSelect={() => {}} teams={view().teams} />);
    expect(chips).toContain("Cancel 63′ substitution");            // the substitution's own minute, not 66′
    expect(chips).toContain("Press higher from 67′");               // the pivot's minute
  });

  it("falls back to at_minute + 1 outside a match", () => {
    expect(optionLabel(cancel, translator("en"))).toBe("Cancel 66′ substitution");
  });
});
