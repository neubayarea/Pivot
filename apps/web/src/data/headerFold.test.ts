// Ax66, Ax77: the slim bar takes over once the header has scrolled up to its last SLIM_H pixels,
// and a press of either button pins the choice.
import { describe, expect, it } from "vitest";
import { SLIM_H, isStuck, slimShown } from "./headerFold";

describe("the slim bar", () => {
  it("takes over when the header's bottom reaches the slim bar's height from the top", () => {
    expect(isStuck(300)).toBe(false);
    expect(isStuck(SLIM_H + 1)).toBe(false);
    expect(isStuck(SLIM_H)).toBe(true);
    expect(isStuck(-500)).toBe(true);
  });

  it("follows the scroll until a button is pressed, then keeps to the choice", () => {
    expect(slimShown("auto", false)).toBe(false);
    expect(slimShown("auto", true)).toBe(true);
    expect(slimShown("full", true)).toBe(false);
    expect(slimShown("full", false)).toBe(false);
    expect(slimShown("slim", false)).toBe(true);
    expect(slimShown("slim", true)).toBe(true);
  });
});
