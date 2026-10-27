// Ax61: smooth motion between frames, the ball trail, the event cues, the frame windows, the replay clock and the control bar.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { MatchEvent, TrackingFrame } from "@pivot/contracts";
import ControlBar from "../components/ControlBar";
import { EventCues, smoothFor } from "../components/motion";
import { PrefsProvider } from "../i18n";
import { framesAround } from "./live/frames";
import { ballTrail, cueOf, cuesAt, cueSpan, indexAt, poseAt, smoothPose, trimJumps } from "./motion";
import { clockAfter } from "./replayClock";

const pl = (player_id: string, x: number, y: number) => ({ player_id, x, y, fitness: 1, speed_ms: 0 });
const frame = (t: number, x: number, owner: string | null = null, ball = x): TrackingFrame => ({
  match_id: "m", t, period: 1, possession: "home",
  ball: { x: ball, y: 34, z: 0, owner_id: owner },
  players: [pl("h9", x, 30), pl("a4", 100 - x, 40)],
});
const ev = (o: Partial<MatchEvent>) =>
  ({ event_id: `e${o.t}`, t: 0, team: "home", type: "pass", location: [10, 10], end_location: [30, 20], meta: {}, ...o }) as MatchEvent;

describe("motion between frames", () => {
  // A player running at an even 10 m/s.
  const run = [0, 1, 2, 3, 4].map((t) => frame(t, 10 * t));

  it("finds the frame at or before the clock", () => {
    expect(indexAt(run, 2.5)).toBe(2);
    expect(indexAt(run, -1)).toBe(0);
    expect(indexAt(run, 9)).toBe(4);
  });

  it("glides through the fraction of a second, with no jolt at whole seconds", () => {
    expect(poseAt(run, 1.5)!.players.get("h9")![0]).toBeCloseTo(15);
    expect(poseAt(run, 2.25)!.players.get("a4")![0]).toBeCloseTo(77.5);
    // Even pace in, even pace out: just before and just after a whole second move the same distance.
    const at = (t: number) => poseAt(run, t)!.players.get("h9")![0];
    expect(at(2) - at(1.99)).toBeCloseTo(at(2.01) - at(2), 4);
  });

  it("holds still across a gap in the frames instead of sliding over it", () => {
    const gap = [frame(0, 10), frame(10, 90)];
    expect(poseAt(gap, 5)!.players.get("h9")![0]).toBe(10);
  });

  it("keeps the ball on its carrier's feet while he has it, and flies it straight otherwise", () => {
    const carried = [frame(0, 0, "h9"), frame(1, 10, "h9"), frame(2, 20, "h9"), frame(3, 30, "h9")];
    const p = poseAt(carried, 1.5)!;
    expect(p.ball[0]).toBeCloseTo(p.players.get("h9")![0]);
    expect(p.owner).toBe("h9");
    const loose = [frame(0, 0, null, 0), frame(1, 0, null, 40)];
    expect(poseAt(loose, 0.25)!.ball[0]).toBeCloseTo(10);
  });

  it("smooths fast replays over a window but leaves a slow one exact", () => {
    expect(smoothFor(1)).toBe(0);
    expect(smoothFor(5)).toBe(0);
    expect(smoothFor(20)).toBe(1);
    const zig = [0, 1, 2, 3, 4].map((t) => frame(t, t % 2 ? 20 : 10));
    expect(smoothPose(zig, 2, 1)!.players.get("h9")![0]).toBeCloseTo(15);
    expect(smoothPose(zig, 2, 0)!.players.get("h9")![0]).toBe(10);
  });

  it("draws a short trail behind the ball and cuts it at a restart", () => {
    const pts = ballTrail(run, 3, 1, 4);
    expect(pts).toHaveLength(5);
    expect(pts[0][0]).toBeCloseTo(20);
    expect(pts.at(-1)![0]).toBeCloseTo(30);
    expect(trimJumps([[0, 0], [1, 0], [52, 34], [53, 34]])).toEqual([[52, 34], [53, 34]]);
  });
});

describe("frame windows", () => {
  it("stitches the frames around the clock across two windows", () => {
    const chunks = new Map([[0, [297, 298, 299].map((t) => frame(t, 0))], [1, [300, 301, 302].map((t) => frame(t, 0))]]);
    expect(framesAround(chunks, 299.5).map((f) => f.t)).toEqual([297, 298, 299, 300, 301]);
    expect(framesAround(chunks, 300.2).map((f) => f.t)).toEqual([298, 299, 300, 301, 302]);
    expect(framesAround(chunks, 700)).toEqual([]);
  });
});

describe("replay clock", () => {
  it("runs on the wall clock at the speed and stops at the end", () => {
    expect(clockAfter(60, 500, 2, 5400)).toBe(61);
    expect(clockAfter(60, 1000, 0.5, 5400)).toBe(60.5);
    expect(clockAfter(5399, 10_000, 20, 5400)).toBe(5400);
    expect(clockAfter(60, -50, 1, 5400)).toBe(60);
  });
});

describe("event cues", () => {
  it("turns passes, shots, tackles, fouls and cards into cues, and nothing else", () => {
    expect(cueOf(ev({ type: "pass" }))?.kind).toBe("pass");
    expect(cueOf(ev({ type: "pass", end_location: null }))).toBeNull();
    expect(cueOf(ev({ type: "shot", shot_outcome: "goal" }))?.kind).toBe("goal");
    expect(cueOf(ev({ type: "shot", shot_outcome: "saved" }))?.kind).toBe("shot");
    expect(cueOf(ev({ type: "interception" }))).toMatchObject({ kind: "tackle", to: null });
    expect(cueOf(ev({ type: "foul" }))?.kind).toBe("foul");
    expect(cueOf(ev({ type: "card", meta: { card: "yellow" } }))?.kind).toBe("yellow");
    expect(cueOf(ev({ type: "card", meta: { card: "red" } }))?.kind).toBe("red");
    expect(cueOf(ev({ type: "pressure" }))).toBeNull();
    expect(cueOf(ev({ type: "pass", location: null }))).toBeNull();
  });

  it("shows what happened in the last few seconds, newest last, a goal for longer", () => {
    // Newest first, as the board has them.
    const events = [ev({ t: 100 }), ev({ t: 98, type: "pressure" }), ev({ t: 96 }), ev({ t: 93.5, type: "shot", shot_outcome: "goal" }), ev({ t: 90 })];
    expect(cuesAt(events, 100, 2.5).map((c) => c.t)).toEqual([100]);
    expect(cuesAt(events, 99, 5).map((c) => c.t)).toEqual([93.5, 96]);
    expect(cuesAt(events, 99.5, 2.5).map((c) => c.kind)).toEqual(["goal"]);
    expect(cuesAt(events, 100, 30, 2).map((c) => c.t)).toEqual([96, 100]);
    expect(cueSpan(1)).toBe(2.5);
    expect(cueSpan(20)).toBe(30);
  });

  it("draws a pass as a line in the team's colour and a goal with its ring", () => {
    const html = renderToStaticMarkup(<svg><EventCues cues={[cueOf(ev({ t: 1, team: "away" }))!, cueOf(ev({ t: 2, type: "shot", shot_outcome: "goal", end_location: [105, 34] }))!]} /></svg>);
    expect(html).toContain('data-cue="pass"');
    expect(html).toContain('stroke="var(--pv-away)"');
    expect(html).toContain('data-cue="goal"');
    // Kept inside the pitch, not on the goal line.
    expect(html).toContain('cx="516"');
  });
});

describe("control bar", () => {
  const bar = () => renderToStaticMarkup(
    <PrefsProvider>
      <ControlBar playing={false} onPlaying={() => {}} value={600} min={0} max={5400} onSeek={() => {}} step={10}
        speeds={[0.5, 1, 2, 5]} speed={20} onSpeed={() => {}} format={(t) => `${t / 60}:00`}
        marks={[{ t: 2700, kind: "goal", side: "home", label: "45′ Goal · HBC" }, { t: 9999, kind: "pivot", label: "x" }]} />
    </PrefsProvider>,
  );

  it("has play, back and on, the timeline with its marks, the time and the speeds", () => {
    const html = bar();
    expect(html).toContain('aria-label="Play"');
    expect(html).toContain("−10s");
    expect(html).toContain('aria-label="Back 10 seconds"');
    expect(html).toContain('class="ctl-mk goal home" style="left:50%"');
    expect(html).toContain('aria-label="45′ Goal · HBC"');
    // A mark past the end of the timeline is not drawn.
    expect(html).not.toContain('aria-label="x"');
    expect(html).toContain("10:00");
    // A speed set from the replay bar still shows, picked.
    expect(html).toMatch(/aria-pressed="true"[^>]*>20×/);
  });
});
