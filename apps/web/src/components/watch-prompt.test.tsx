// C13 (#316): the fan / analyst question is asked once, only when nothing chose a mode yet.
import { describe, expect, it } from "vitest";
import { shouldAsk } from "./WatchPrompt";

const storage = (items: Record<string, string>) => ({ getItem: (k: string) => items[k] ?? null });

describe("first-visit question", () => {
  it("asks a first-time visitor", () => {
    expect(shouldAsk("?match=M-seed-101", storage({}))).toBe(true);
  });
  it("never asks when the link already says the mode (a recording)", () => {
    expect(shouldAsk("?mode=fan", storage({}))).toBe(false);
  });
  it("does not ask again after a choice, a close, or with storage blocked", () => {
    expect(shouldAsk("", storage({ "pivot.mode": "analyst" }))).toBe(false);
    expect(shouldAsk("", storage({ "pivot.asked": "1" }))).toBe(false);
    expect(shouldAsk("", null)).toBe(false);
    expect(shouldAsk("", { getItem: () => { throw new Error("blocked"); } })).toBe(false);
  });
});
