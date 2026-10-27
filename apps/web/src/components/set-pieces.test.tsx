// Ax56: corners, free kicks and penalties replayed in the clip player shared with the key moments.
// What each set piece's clip covers, penalties found from the foul that gave them, then the board
// on the M-seed-29 demo match (40′ corner goal, 60′ penalty saved).
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Match, MatchEvent } from "@pivot/contracts";
// a recorded match that never changes (eval/frozen/README.md: M-seed-29 before Ax44)
import demo from "../../../../eval/frozen/m-seed-29-before-ax44.json";
import { RATES, SET_AFTER, SET_BEFORE, SET_KEPT, setPieceClip } from "../data/clips";
import { toView } from "../data/live/provider";
import { MatchContext } from "../data/match";
import { setPieces, shotClips, tally } from "../data/setpieces";
import { SetPieceBoard } from "./SetPieces";

let seq = 0;
const ev = (o: Partial<MatchEvent>) =>
  ({ event_id: `e${++seq}`, seq, t: 0, period: 1, period_t: 0, team: "home", type: "pass", meta: {}, pass_type: null, play_pattern: "open_play",
    possession_id: 1, player_id: "h9", receiver_id: null, location: [50, 34], end_location: null, shot_outcome: null, foul: null, var: null,
    keeper_action: null, xg: null, clock_label: "1'", substitution: null, team_sheet: null, ...o }) as MatchEvent;

describe("a set piece's clip", () => {
  const corner = ev({ t: 100, player_id: "h7", pass_type: "corner", location: [105, 68] });

  it("runs from the players lining up to just after the clearance", () => {
    const clear = ev({ t: 104, team: "away", player_id: "a4", type: "clearance", location: [100, 34] });
    const events = [ev({ t: 90, type: "carry" }), corner, ev({ t: 102, type: "pass", player_id: "h4" }), clear, ev({ t: 120, type: "pass" })];
    const sp = setPieces(events)[0];
    const c = setPieceClip(sp, events);
    expect(c.parts).toEqual([[100 - SET_BEFORE, 104 + SET_AFTER]]);
    expect(c.events.map((e) => e.t)).toEqual([100, 102, 104]);
    expect(c.involved).toEqual(["h7", "a4"]);
    expect([c.shot, c.marks]).toEqual([null, []]);
  });

  it("flies the ball of the shot that settled it and marks a goal", () => {
    const shot = ev({ t: 103, type: "shot", player_id: "h5", shot_outcome: "goal", location: [99, 34], end_location: [105, 33] });
    const c = setPieceClip(setPieces([corner, shot])[0], [corner, shot]);
    expect(c.parts).toEqual([[97, 106]]);
    expect(c.shot).toBe(shot);
    expect(c.marks).toEqual([{ t: 103, kind: "goal", side: "home", at: [99, 34] }]);
  });

  it("runs on a few seconds when nothing settles it, and never before kick-off", () => {
    const early = ev({ t: 1, pass_type: "free_kick", location: [90, 34] });
    expect(setPieceClip(setPieces([early])[0], [early]).parts).toEqual([[0, 1 + SET_KEPT + SET_AFTER]]);
  });
});

describe("penalties", () => {
  const foul = ev({ t: 1000, team: "away", type: "foul", foul: { penalty_awarded: true } as MatchEvent["foul"] });

  it("are the kick after the foul that gave them, whatever the possession's pattern", () => {
    const kick = ev({ t: 1060, type: "shot", play_pattern: "counter", location: [94, 34], shot_outcome: "saved", end_location: [105, 36] });
    const list = setPieces([foul, kick]);
    expect(list.map((s) => [s.kind, s.zone, s.result])).toEqual([["penalty", null, "shot"]]);
    expect(tally(list).home).toEqual({ corners: 0, freeKicks: 0, penalties: 1, shots: 1, goals: 0 });
    expect(setPieceClip(list[0], [foul, kick]).parts).toEqual([[1057, 1063]]);
  });

  it("leave a shootout's kicks out", () => {
    const shootout = ev({ t: 7000, period: 5, type: "shot", play_pattern: "penalty", shootout_round: 1, location: [94, 34] });
    expect(setPieces([shootout])).toEqual([]);
  });
});

// The frozen match (eval/frozen): M-seed-29 as it was before Ax44.
const fx = demo as unknown as { match: Match; events: MatchEvent[] };

describe("on the M-seed-29 demo match", () => {
  it("lists the 60′ penalty with the corners and calls its shot a set piece", () => {
    const pen = setPieces(fx.events).find((s) => s.kind === "penalty")!;
    expect([pen.event.t, pen.result]).toEqual([3692, "shot"]);
    expect(setPieceClip(pen, fx.events).parts).toEqual([[3689, 3695]]);
    expect(shotClips(fx.events).find((c) => c.shot.t === 3692)?.source).toBe("set_piece");
  });

  it("opens the first one in the clip player, with its speeds", () => {
    const view = toView({ match: fx.match, events: [...fx.events].reverse(), metrics: [], pivots: [] });
    const html = renderToStaticMarkup(<MatchContext.Provider value={view}><SetPieceBoard /></MatchContext.Provider>);
    expect(html).toContain("Penalty");
    // One of each is singular (Ax69): "1 penalty", "1 goal", not "1 penalties", "1 goals".
    expect(html).toMatch(/1 penalty led to 2 shots and 1 goal</);
    expect(html).toContain("led to 1 shot and 1 goal");
    expect(html.match(/class="clip[" ]/g)).toHaveLength(1);
    expect(html).toContain('aria-label="Replay: ');
    for (const r of RATES) expect(html).toContain(`${r}×`);
    expect(html).toContain("from 3 seconds before the kick");
    // Ax57: marking and walls are shown again, so the how-to names the marker lines and the simulator note is gone.
    expect(html).toContain("dashed lines join each attacker to their marker");
    expect(html).not.toContain("does not yet line players up");
  });
});
