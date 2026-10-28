// The pass network read two ways (C21, #401): the API's edges run one way (from -> to); a pair
// is both directions added up. The most involved player is the one with the most completed passes
// made and received (weighted degree, from the same report). Nothing here counts a pass itself.
import type { PassNetworkEdge, PassNetworkNode } from "@pivot/contracts";

export type Pair = { a: string; b: string; passes: number; ab: number; ba: number };

/** Each pair of players with a line, both directions together, most passes first. */
export function pairs(edges: readonly PassNetworkEdge[]): Pair[] {
  const by = new Map<string, Pair>();
  for (const e of edges) {
    const [a, b] = e.from_id < e.to_id ? [e.from_id, e.to_id] : [e.to_id, e.from_id];
    const key = `${a}|${b}`;
    const p = by.get(key) ?? { a, b, passes: 0, ab: 0, ba: 0 };
    p.passes += e.passes;
    if (e.from_id === a) p.ab += e.passes; else p.ba += e.passes;
    by.set(key, p);
  }
  return [...by.values()].sort((x, y) => y.passes - x.passes || x.a.localeCompare(y.a) || x.b.localeCompare(y.b));
}

export const FAN_PAIRS = 5;

/** The player with the most completed passes made and received; null with no one on the ball. */
export function mostInvolved(nodes: readonly PassNetworkNode[]): PassNetworkNode | null {
  return nodes.reduce<PassNetworkNode | null>((best, n) => {
    const v = n.passes + n.received;
    return v > 0 && (!best || v > best.passes + best.received) ? n : best;
  }, null);
}
