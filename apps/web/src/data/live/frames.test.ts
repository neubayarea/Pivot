import { describe, expect, it } from "vitest";
import type { TrackingFrame } from "@pivot/contracts";
import { CHUNK_S, chunkOf, frameAt } from "./frames";

const frame = (t: number) => ({ match_id: "m1", t, period: 1, possession: null, players: [], ball: { x: 0, y: 0 } }) as unknown as TrackingFrame;

describe("pitch board frames", () => {
  it("asks for five-minute windows", () => {
    expect(CHUNK_S).toBe(300);
    expect([0, 299, 300, 5999, -4].map(chunkOf)).toEqual([0, 0, 1, 19, 0]);
  });

  it("draws the last frame at or before the clock", () => {
    const frames = [0, 1, 2, 4, 5].map(frame);
    expect(frameAt(frames, 2)?.t).toBe(2);
    expect(frameAt(frames, 3)?.t).toBe(2);
    expect(frameAt(frames, 99)?.t).toBe(5);
    expect(frameAt(frames, -1)?.t).toBe(0);
    expect(frameAt([], 3)).toBeNull();
  });
});
