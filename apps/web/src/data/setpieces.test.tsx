// Ax37: set pieces, what came of them, the setup at the kick, and the shot clips. The rules run on
// hand-made events and frames, then over the M-seed-29 demo match the board shows. Static HTML, no DOM.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Match, MatchEvent, TrackingFrame } from "@pivot/contracts";
import { SetPieceBoard, ShotBoard } from "../components/SetPieces";
import demo from "../../../../eval/fixtures/demo-1021.json";
import { toView } from "./live/provider";
import { MatchContext } from "./match";
import { clipBall, frameBefore, frameBetween, freeKickZone, resultOf, setPieces, setupAt, shotClips, tally } from "./setpieces";

let seq = 0;
const ev = (o: Partial<MatchEvent>) =>
  ({ event_id: `e${++seq}`, seq, t: 0, team: "home", type: "pass", meta: {}, pass_type: null, play_pattern: "open_play",
    possession_id: 1, player_id: "h9", receiver_id: null, location: [50, 34], end_location: null, shot_outcome: null,
    keeper_action: null, xg: null, clock_label: "1'", substitution: null, team_sheet: null, ...o }) as MatchEvent;
const at = (player_id: string, x: number, y: number) => ({ player_id, x, y, fitness: 1, speed_ms: 0 });
const frame = (t: number, players: ReturnType<typeof at>[], ball: [number, number] = [105, 68]): TrackingFrame =>
  ({ match_id: "m", t, period: 1, possession: "home", ball: { x: ball[0], y: ball[1], z: 0, owner_id: null }, players });
const isHome = (id: string) => id.startsWith("h");
const isKeeper = (id: string) => id.endsWith("1") && id.length === 2;

describe("set piece results", () => {
  const corner = ev({ t: 100, pass_type: "corner", location: [105, 68] });

  it("is a goal or shot when the takers shoot within 15 s", () => {
    expect(resultOf(corner, [ev({ t: 103, type: "shot", shot_outcome: "goal" })]).result).toBe("goal");
    expect(resultOf(corner, [ev({ t: 103, type: "shot", shot_outcome: "saved" })]).result).toBe("shot");
    expect(resultOf(corner, [ev({ t: 116, type: "shot" })]).result).toBe("kept");
  });

  it("is cleared by a clearance or keeper claim, lost when the defenders win it otherwise", () => {
    expect(resultOf(corner, [ev({ t: 101, team: "away", type: "clearance" })]).result).toBe("cleared");
    expect(resultOf(corner, [ev({ t: 101, team: "away", type: "goalkeeper", keeper_action: "claim" })]).result).toBe("cleared");
    expect(resultOf(corner, [ev({ t: 101, team: "away", type: "pressure" }), ev({ t: 102, team: "away", type: "ball_recovery" })]).result).toBe("lost");
    expect(resultOf(corner, [ev({ t: 101, type: "offside" })]).result).toBe("lost");
  });

  it("finds corners and free kicks and sorts free kicks by distance from goal", () => {
    const list = setPieces([
      ev({ t: 10, pass_type: "free_kick", location: [85, 30] }),            // 21 m from the right goal
      ev({ t: 20, pass_type: "free_kick", location: [72, 5] }),             // attacking third, wide
      ev({ t: 30, team: "away", pass_type: "free_kick", location: [70, 34] }), // away attack left: their own half
      corner, ev({ t: 40, type: "pass" }),
    ]);
    expect(list.map((s) => [s.event.t, s.kind, s.zone])).toEqual([
      [10, "free_kick", "shooting"], [20, "free_kick", "attacking"], [30, "free_kick", "deep"], [100, "corner", null],
    ]);
    expect(freeKickZone(ev({ team: "away", location: [20, 34] }))).toBe("shooting");
  });
});

describe("the setup at the kick", () => {
  const corner = setPieces([ev({ t: 100, player_id: "h7", pass_type: "corner", location: [105, 68] })])[0];

  it("counts the box and reads tight pairs as man-to-man", () => {
    const f = frame(99, [at("h7", 105, 68), at("h2", 98, 30), at("h3", 96, 38), at("h4", 100, 34),
      at("a1", 104, 34), at("a2", 99, 31), at("a3", 97, 39), at("a4", 101, 35), at("a5", 60, 34)]);
    const s = setupAt(f, corner, isHome, isKeeper);
    expect(s.attackersInBox).toEqual(["h2", "h3", "h4"]);
    expect(s.defendersInBox).toHaveLength(4);
    expect(s.pairs).toHaveLength(3);
    expect(s.marking).toBe("man");
  });

  it("reads defenders holding spaces away from the attackers as zonal", () => {
    const f = frame(99, [at("h2", 98, 30), at("h3", 96, 38), at("h4", 100, 34), at("a2", 102, 26), at("a3", 102, 42), at("a4", 94, 34)]);
    expect(setupAt(f, corner, isHome, isKeeper).marking).toBe("zonal");
  });

  it("finds a free kick's wall between the ball and the goal", () => {
    const fk = setPieces([ev({ t: 50, pass_type: "free_kick", location: [80, 34] })])[0];
    const f = frame(49, [at("a2", 88, 33), at("a3", 88, 35), at("a4", 80, 50), at("a1", 104, 34)], [80, 34]);
    expect(setupAt(f, fk, isHome, isKeeper).wall).toEqual(["a2", "a3"]);
  });

  it("reads the frame just before the kick", () => {
    expect(frameBefore([frame(98, []), frame(99, []), frame(100, [])], 100)?.t).toBe(99);
    expect(frameBefore([frame(100, [])], 100)?.t).toBe(100);
  });
});

describe("shot clips", () => {
  it("start with the attack, but 5 to 15 s before the shot, and end 2 s after", () => {
    const events = [ev({ t: 50, possession_id: 3 }), ev({ t: 60, possession_id: 3 }), ev({ t: 70, possession_id: 3, type: "shot" }),
      ev({ t: 200, possession_id: 4 }), ev({ t: 203, possession_id: 4, type: "shot" })];
    expect(shotClips(events).map((c) => [c.from, c.to, c.chain.length])).toEqual([[55, 72, 2], [198, 205, 2]]);
  });

  it("names the source: a corner just before is a set piece, a counter a counter", () => {
    const events = [ev({ t: 10, possession_id: 1, pass_type: "corner" }), ev({ t: 13, possession_id: 1, type: "shot" }),
      ev({ t: 90, possession_id: 2, play_pattern: "counter", type: "shot" }), ev({ t: 150, possession_id: 5, type: "shot" })];
    expect(shotClips(events).map((c) => c.source)).toEqual(["set_piece", "counter", "open_play"]);
  });

  it("moves the dots in a straight line between frames", () => {
    const f = frameBetween([frame(10, [at("h2", 10, 10)], [0, 0]), frame(11, [at("h2", 20, 30)], [10, 0])], 10.25);
    expect(f?.players[0]).toMatchObject({ x: 12.5, y: 15 });
    expect(f?.ball.x).toBe(2.5);
  });

  it("flies the ball to the shot's end point instead of the frames' reset after a goal", () => {
    const [clip] = shotClips([ev({ t: 20, possession_id: 1, type: "shot", location: [95, 34], end_location: [105, 34] })]);
    const fs = [frame(19, [], [95, 34]), frame(20, [], [52.5, 34])];
    expect(clipBall(clip, fs, 18)).toBeNull();
    expect(clipBall(clip, fs, 19.5)).toEqual({ x: 100, y: 34 });
    expect(clipBall(clip, fs, 21)).toEqual({ x: 105, y: 34 });
  });
});

// The demo match the board shows: M-seed-29, Harbour City v the away side.
const fx = demo as unknown as { match: Match; events: MatchEvent[] };

describe("on the M-seed-29 demo match", () => {
  const list = setPieces(fx.events);

  it("has its 11 corners and the corner goal at 40′", () => {
    expect(list.filter((s) => s.kind === "corner")).toHaveLength(11);
    const goal = list.find((s) => s.event.t === 2388)!;
    expect([goal.kind, goal.result, goal.decidedBy?.t]).toEqual(["corner", "goal", 2391]);
    const shown = tally(list.filter((s) => s.kind === "corner" || s.zone !== "deep"));
    expect(shown.home.goals + shown.away.goals).toBe(2);
  });

  it("clips all 19 shots, the corner goal as a set piece", () => {
    const clips = shotClips(fx.events);
    expect(clips).toHaveLength(19);
    expect(clips.find((c) => c.shot.t === 2391)?.source).toBe("set_piece");
    expect(clips.find((c) => c.shot.t === 3692)?.source).toBe("counter");
  });

  it("lists them on the board with their results", () => {
    const view = toView({ match: fx.match, events: [...fx.events].reverse(), metrics: [], pivots: [] });
    const html = (el: React.ReactNode) => renderToStaticMarkup(<MatchContext.Provider value={view}>{el}</MatchContext.Provider>);
    const set = html(<SetPieceBoard />);
    expect(set).toContain("Corner");
    expect(set).toContain("Goal");
    expect(set).toContain("Also show free kicks far from goal");
    const shots = html(<ShotBoard />);
    expect(shots).toContain("All 19");
    expect(shots).toContain("xG 0.31");
    expect(shots.match(/class="sh-card /g)).toHaveLength(19);
  });
});
