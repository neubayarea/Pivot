// C21 (#401): "who is on top now" comes from the run of play (momentum) over the last ten minutes,
// and says nothing when it is close or there is too little of it.
import { describe, expect, it } from "vitest";
import type { MinuteMetric } from "@pivot/contracts";
import { onTopNow } from "./LiveCentre";

const m = (minute: number, momentum: number) => ({ minute, momentum } as MinuteMetric);

describe("who is on top now", () => {
  it("reads the last ten minutes", () => {
    const run = [...Array(20)].map((_, i) => m(i + 1, i < 10 ? -0.5 : 0.4));
    expect(onTopNow(run, 20)).toBe("home");
    expect(onTopNow(run, 10)).toBe("away");
  });
  it("says nothing when it is close or too short", () => {
    expect(onTopNow([m(1, 0.02), m(2, -0.03), m(3, 0.01)], 3)).toBeNull();
    expect(onTopNow([m(1, 0.9), m(2, 0.9)], 2)).toBeNull();
  });
});
