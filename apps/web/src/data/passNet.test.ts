// C21 (#401): the pass network in pairs (both directions added up) and its most involved player.
import { describe, expect, it } from "vitest";
import type { PassNetworkEdge, PassNetworkNode } from "@pivot/contracts";
import { FAN_PAIRS, mostInvolved, pairs } from "./passNet";

const edge = (from_id: string, to_id: string, passes: number) => ({ from_id, to_id, passes }) as PassNetworkEdge;
const node = (player_id: string, passes: number, received: number) => ({ player_id, x: 50, y: 34, passes, received }) as PassNetworkNode;

describe("pairs", () => {
  it("adds up both directions and puts the busiest first", () => {
    const out = pairs([edge("b", "a", 4), edge("a", "b", 6), edge("c", "d", 9), edge("a", "c", 3)]);
    expect(out).toEqual([
      { a: "a", b: "b", passes: 10, ab: 6, ba: 4 },
      { a: "c", b: "d", passes: 9, ab: 9, ba: 0 },
      { a: "a", b: "c", passes: 3, ab: 3, ba: 0 },
    ]);
    expect(pairs([])).toEqual([]);
  });
  it("gives a fan the five busiest", () => {
    const many = Array.from({ length: 8 }, (_, i) => edge(`p${i}`, `q${i}`, 10 + i));
    expect(pairs(many).slice(0, FAN_PAIRS).map((p) => p.passes)).toEqual([17, 16, 15, 14, 13]);
  });
});

describe("the most involved player", () => {
  it("has the most passes made and received", () => {
    expect(mostInvolved([node("a", 20, 10), node("b", 15, 25), node("c", 0, 0)])?.player_id).toBe("b");
    expect(mostInvolved([node("a", 0, 0)])).toBeNull();
    expect(mostInvolved([])).toBeNull();
  });
});
