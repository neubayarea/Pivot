// C13 QA round 3: the story of the match tells each moment once. A goal or red card that set a
// turning point off, or came in its minute, is a line on that card; the rest keep their own card.
import { describe, expect, it } from "vitest";
import type { MatchEvent, Pivot1 as Pivot } from "@pivot/contracts";
import type { KeyMoment } from "../data/keyMoments";
import { storyItems } from "./MatchStory";

const pivot = (id: string, minute: number, direction: "home" | "away", trigger_event_ids: string[] = []) =>
  ({ pivot_id: id, minute, direction, status: "confirmed", trigger_event_ids } as unknown as Pivot);
const key = (id: string, t: number, side: "home" | "away", kind: KeyMoment["kind"] = "goal") =>
  ({ event: { event_id: id, t, clock_label: `${Math.floor(t / 60) + 1}'` } as MatchEvent, kind, side, situation: "equaliser" } as KeyMoment);

describe("storyItems", () => {
  it("folds a goal into the turning point it set off, or one in the same minute", () => {
    const items = storyItems(
      [pivot("p13", 13, "away"), pivot("p34", 34, "away"), pivot("p74", 74, "home", ["g72"])],
      [key("g34", 34 * 60 + 20, "away"), key("g72", 71 * 60 + 5, "home"), key("g50", 50 * 60, "home")],
    );
    expect(items.map((i) => i.id)).toEqual(["p13", "p34", "g50", "p74"]);
    expect(items[1].also?.map((k) => k.event.event_id)).toEqual(["g34"]);
    expect(items[3].also?.map((k) => k.event.event_id)).toEqual(["g72"]);
  });

  it("keeps a goal of its own when no turning point is near, and stops at four cards", () => {
    const items = storyItems(
      [pivot("p20", 20, "home")],
      [key("g5", 300, "home"), key("g40", 2400, "away"), key("g60", 3600, "home"), key("r80", 4800, "away", "red")],
    );
    expect(items).toHaveLength(4);
    expect(items.map((i) => i.id)).toEqual(["g5", "p20", "g40", "g60"]);
    expect(items.every((i) => !i.also)).toBe(true);
  });
});
