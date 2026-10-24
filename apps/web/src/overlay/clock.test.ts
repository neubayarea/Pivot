import { describe, expect, it } from "vitest";
import type { OverlayCard } from "@pivot/contracts";
import { cardAt, clockMode, MAX_CLOCK, parseClock, replayClock, severityDots } from "./clock";

const card = (id: string, show_at: number, hide_at: number) => ({ pivot_id: id, show_at, hide_at }) as OverlayCard;
// Two cards, the first cut short by the second as the API does.
const cards = [card("p61", 3665, 3677), card("p70", 4200, 4212), card("p71", 4212, 4224)];

describe("cardAt", () => {
  it("shows a card from show_at up to, not including, hide_at", () => {
    expect(cardAt(cards, 3664)).toBeNull();
    expect(cardAt(cards, 3665)?.pivot_id).toBe("p61");
    expect(cardAt(cards, 3676)?.pivot_id).toBe("p61");
    expect(cardAt(cards, 3677)).toBeNull();
  });

  it("hands over to the next card in the same second, never showing two", () => {
    expect(cardAt(cards, 4211)?.pivot_id).toBe("p70");
    expect(cardAt(cards, 4212)?.pivot_id).toBe("p71");
  });

  it("shows nothing with no cards", () => {
    expect(cardAt([], 3665)).toBeNull();
  });
});

describe("parseClock", () => {
  it("reads mm:ss and plain seconds like the API", () => {
    expect(parseClock("61:10")).toBe(3670);
    expect(parseClock(" 3670 ")).toBe(3670);
    expect(parseClock("105:00")).toBe(6300);
  });

  it("rejects anything else", () => {
    for (const bad of [null, "", "61:7", "61:60", "-5", "1.5", "abc", String(MAX_CLOCK + 1)]) {
      expect(parseClock(bad)).toBeNull();
    }
  });
});

describe("clockMode", () => {
  const mode = (q: string) => clockMode(new URLSearchParams(q));

  it("follows the live match by default", () => {
    expect(mode("")).toEqual({ kind: "live" });
    expect(mode("preview=1")).toEqual({ kind: "live" });
  });

  it("holds a fixed moment with ?clock=", () => {
    expect(mode("clock=61:10")).toEqual({ kind: "fixed", at: 3670 });
  });

  it("replays from ?clock= (or kick-off) at ?speed=", () => {
    expect(mode("speed=20")).toEqual({ kind: "replay", from: 0, speed: 20 });
    expect(mode("clock=61:00&speed=4")).toEqual({ kind: "replay", from: 3660, speed: 4 });
  });

  it("ignores a speed that is not a positive number", () => {
    expect(mode("speed=0")).toEqual({ kind: "live" });
    expect(mode("speed=fast&clock=10:00")).toEqual({ kind: "fixed", at: 600 });
  });
});

describe("replayClock", () => {
  it("runs speed match seconds per wall second, in whole seconds", () => {
    const m = { from: 3660, speed: 20 };
    expect(replayClock(m, 0)).toBe(3660);
    expect(replayClock(m, 250)).toBe(3665);
    expect(replayClock(m, 1000)).toBe(3680);
  });

  it("puts the demo card on screen for 12 match seconds at speed 20", () => {
    const m = { from: 3660, speed: 20 };
    const onScreen = [0, 200, 250, 500, 800, 850].map((ms) => cardAt(cards, replayClock(m, ms))?.pivot_id ?? null);
    expect(onScreen).toEqual([null, null, "p61", "p61", "p61", null]);
  });

  it("stops at the end of any match", () => {
    expect(replayClock({ from: MAX_CLOCK - 1, speed: 10 }, 5000)).toBe(MAX_CLOCK);
  });
});

describe("severityDots", () => {
  it("fills one dot per severity step", () => {
    expect(severityDots(1)).toBe("●○○");
    expect(severityDots(3)).toBe("●●●");
  });
});
