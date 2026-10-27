// Ax66: the score header folds with the scroll, with a dead band so it cannot flicker, and a press
// of its button holds until the scroll argues back.
import { describe, expect, it } from "vitest";
import { FOLD_START, RELEASE_PX, SLIM_H, foldReducer, isSlim, linesFor, type FoldState } from "./headerFold";

// The header starts 60px down the page (under the site bar) and is 200px tall in full.
const lines = linesFor(60, 200);
const scroll = (s: FoldState, ...ys: number[]) => ys.reduce((st, y) => foldReducer(st, { type: "scroll", y, lines }), s);
const toggle = (s: FoldState, y: number) => foldReducer(s, { type: "toggle", y, lines });

describe("folding with the scroll", () => {
  it("puts the lines at the header's bottom and one slim bar above it", () => {
    expect(lines).toEqual({ collapseAt: 260, expandAt: 260 - SLIM_H });
  });

  it("is full at the top and folds once scrolled past the header", () => {
    expect(isSlim(scroll(FOLD_START, 0))).toBe(false);
    expect(isSlim(scroll(FOLD_START, 0, 120, 260))).toBe(false);
    expect(isSlim(scroll(FOLD_START, 0, 120, 261))).toBe(true);
    expect(isSlim(scroll(FOLD_START, 0, 900, 0))).toBe(false);
  });

  it("does not flicker between the two lines", () => {
    const slim = scroll(FOLD_START, 400);
    // Wobbling just under the fold line keeps it slim; it opens only above the upper line.
    expect(isSlim(scroll(slim, 259, 262, 230, 250, 212))).toBe(true);
    expect(isSlim(scroll(slim, 211))).toBe(false);
    // And on the way down it stays full until past the lower line.
    const full = scroll(FOLD_START, 0);
    expect(isSlim(scroll(full, 220, 250, 215, 260))).toBe(false);
  });

  it("opens straight away when the page loads near the top, and folds when it loads deep", () => {
    expect(isSlim(scroll(FOLD_START, 230))).toBe(false);
    expect(isSlim(scroll(FOLD_START, 1500))).toBe(true);
  });

  it("returns the same state when nothing changes, so React skips the render", () => {
    const s = scroll(FOLD_START, 400);
    expect(scroll(s, 410)).toBe(s);
  });
});

describe("the buttons", () => {
  it("opening by hand while scrolled down holds against small scrolls", () => {
    const open = toggle(scroll(FOLD_START, 800), 800);
    expect(isSlim(open)).toBe(false);
    expect(isSlim(scroll(open, 820, 790, 800 + RELEASE_PX))).toBe(false);
    // Scrolling up a long way, but not back to the top, does not fold it either.
    expect(isSlim(scroll(open, 400, 300))).toBe(false);
  });

  it("an opened header folds again after the page scrolls on down", () => {
    const open = toggle(scroll(FOLD_START, 800), 800);
    expect(isSlim(scroll(open, 900, 800 + RELEASE_PX + 1))).toBe(true);
  });

  it("an opened header gives the scroll back once it reaches the top", () => {
    const open = toggle(scroll(FOLD_START, 800), 800);
    const top = scroll(open, 100);
    expect(top.manual).toBeNull();
    expect(isSlim(scroll(top, 400))).toBe(true);
  });

  it("folding by hand holds until the page scrolls up past the top line", () => {
    // Folded at the upper line (App scrolls there first when folded near the top).
    const shut = toggle(scroll(FOLD_START, 0, lines.expandAt), lines.expandAt);
    expect(isSlim(shut)).toBe(true);
    expect(isSlim(scroll(shut, 230, lines.expandAt))).toBe(true);
    expect(isSlim(scroll(shut, lines.expandAt - 1))).toBe(false);
  });

  it("a hand fold becomes the automatic one once scrolled past the header", () => {
    const shut = toggle(scroll(FOLD_START, 0, 230), 230);
    const past = scroll(shut, 600);
    expect(past.manual).toBeNull();
    expect(isSlim(past)).toBe(true);
  });

  it("pressing twice goes back to what the scroll wants, with no choice held", () => {
    const s = scroll(FOLD_START, 800);
    const back = toggle(toggle(s, 800), 800);
    expect(isSlim(back)).toBe(true);
    expect(back.manual).toBeNull();
  });
});
