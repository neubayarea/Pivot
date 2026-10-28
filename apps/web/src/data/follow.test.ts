import { describe, expect, it } from "vitest";
import type { MatchEvent, Pivot1 as Pivot } from "@pivot/contracts";
import { involvedIn, playerMoments } from "./follow";

const ev = (o: Partial<MatchEvent>): MatchEvent => ({
  event_id: `e${o.seq}`, seq: 0, t: 0, team: "home", type: "pass", player_id: null, receiver_id: null, possession_id: 1,
  shot_outcome: null, substitution: null, foul: null, meta: {}, clock_label: "1'", ...o,
} as unknown as MatchEvent);

describe("the followed player's match (Ax92)", () => {
  const events = [
    ev({ seq: 1, t: 100, player_id: "h11", receiver_id: "h09" }),
    ev({ seq: 2, t: 104, type: "shot", player_id: "h09", shot_outcome: "goal" }),
    ev({ seq: 3, t: 600, type: "shot", player_id: "h11", shot_outcome: "saved", possession_id: 2 }),
    ev({ seq: 4, t: 900, type: "shot", player_id: "h11", shot_outcome: "off_target", possession_id: 3 }),
    ev({ seq: 5, t: 1200, type: "card", player_id: "h11", foul: { card: "yellow" } as MatchEvent["foul"], possession_id: 4 }),
    ev({ seq: 6, t: 4000, type: "substitution", substitution: { player_on_id: "h20", player_off_id: "h11", reason: "tactical", slot: 1 }, possession_id: 5 }),
  ];
  it("lists his assist, shots, card and substitution in order", () => {
    expect(playerMoments(events, "h11").map((m) => m.kind)).toEqual(["assist", "shotOn", "shotOff", "yellow", "subOff"]);
    expect(playerMoments(events, "h09").map((m) => m.kind)).toEqual(["goal"]);
  });
  it("tags a turning point he was in, by its events or its ±5 minutes", () => {
    const pivot = { minute: 20, trigger_event_ids: [], narrative: null } as unknown as Pivot;
    const byId = (id: string) => events.find((e) => e.event_id === id);
    expect(involvedIn(pivot, "h11", events, byId)).toBe(true);    // the card at 20′
    expect(involvedIn(pivot, "h09", events, byId)).toBe(false);
    expect(involvedIn({ ...pivot, trigger_event_ids: ["e2"] }, "h09", events, byId)).toBe(true);
  });
});
