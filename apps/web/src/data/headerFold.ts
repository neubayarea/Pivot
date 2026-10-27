// The score header folds into a slim bar once the page scrolls past it, and opens again near the
// top (Ax66). The header's place in the page never changes size: while slim, the sticky
// `.match-head` carries a bottom margin for the rows it folded away, so nothing below it moves and
// the fold cannot feed back into the scroll position that decided it.
//
// Two lines, `SLIM_H` apart, keep it from flickering at the threshold:
// - below `collapseAt` (the header's bottom, where it sat before it stuck) it folds;
// - above `expandAt` (`SLIM_H` higher) it opens, since from there up the folded rows' space would
//   show as a gap under the slim bar.
//
// A press of the button wins over the scroll until the scroll argues back:
// - opened by hand while scrolled down: stays open until the page is scrolled `RELEASE_PX` further
//   down, or back up to where it opens by itself;
// - folded by hand: stays slim until the page scrolls up past `expandAt`, or down past
//   `collapseAt` (where it would fold anyway).
import { useCallback, useEffect, useLayoutEffect, useReducer, useRef, useState } from "react";

/** Height of the slim bar (base.css `.mh.slim`). */
export const SLIM_H = 48;
/** How far past the point where it was opened by hand the page scrolls down before it folds again. */
export const RELEASE_PX = 200;

export type Lines = { expandAt: number; collapseAt: number };

export type FoldState = {
  /** What the scroll alone would show. */
  auto: boolean;
  /** A choice made with the button, and the scroll position it was made at. */
  manual: { slim: boolean; y: number } | null;
};

export type FoldAction =
  | { type: "scroll"; y: number; lines: Lines }
  | { type: "toggle"; y: number; lines: Lines };

export const FOLD_START: FoldState = { auto: false, manual: null };

/** Whether the header is slim now. */
export const isSlim = (s: FoldState) => (s.manual ? s.manual.slim : s.auto);

/** Where the slim/full lines sit, from the header's top before it stuck and its full height. */
export const linesFor = (top: number, fullH: number): Lines => ({ expandAt: top + fullH - SLIM_H, collapseAt: top + fullH });

function autoAt(auto: boolean, y: number, { expandAt, collapseAt }: Lines): boolean {
  if (y > collapseAt) return true;
  if (y < expandAt) return false;
  return auto;
}

function settle(auto: boolean, manual: FoldState["manual"], y: number, lines: Lines): FoldState["manual"] {
  if (!manual || y < lines.expandAt || manual.slim === auto) return null;
  if (!manual.slim && y - manual.y > RELEASE_PX) return null;
  return manual;
}

export function foldReducer(s: FoldState, a: FoldAction): FoldState {
  const auto = autoAt(s.auto, a.y, a.lines);
  if (a.type === "toggle") {
    const slim = !isSlim(s);
    return { auto, manual: slim === auto ? null : { slim, y: a.y } };
  }
  const manual = settle(auto, s.manual, a.y, a.lines);
  return auto === s.auto && manual === s.manual ? s : { auto, manual };
}

export type HeaderFold = {
  slim: boolean;
  toggle: () => void;
  /** A zero-height marker just before `.match-head`: where the header starts before it sticks. */
  anchor: (el: HTMLDivElement | null) => void;
  /** The sticky `.match-head` itself. */
  head: (el: HTMLDivElement | null) => void;
};

/** Folds the score header with the scroll; `toggle` is the header's own button. */
export function useHeaderFold(): HeaderFold {
  const [state, dispatch] = useReducer(foldReducer, FOLD_START);
  // Elements, not refs: the match head mounts only once the live feed has a match (MatchProvider).
  const [anchor, setAnchor] = useState<HTMLDivElement | null>(null);
  const [head, setHead] = useState<HTMLDivElement | null>(null);
  const fullH = useRef(0);
  const slim = isSlim(state);

  const lines = useCallback((): Lines | null => {
    if (!anchor || !fullH.current) return null;
    return linesFor(anchor.getBoundingClientRect().top + window.scrollY, fullH.current);
  }, [anchor]);

  // The full header's height, and the margin that stands in for it while slim. Written straight to
  // the DOM before paint, so the frame that shows the slim bar already has the margin under it.
  const reserve = useCallback(() => {
    const mh = head?.querySelector<HTMLElement>(".mh");
    if (!mh || !head) return;
    const folded = mh.classList.contains("slim");
    const h = mh.getBoundingClientRect().height;
    if (!folded) fullH.current = h;
    head.style.setProperty("--mh-reserve", `${folded ? Math.max(0, fullH.current - h) : 0}px`);
  }, [head]);

  useLayoutEffect(reserve, [slim, reserve]);
  useEffect(() => {
    const mh = head?.querySelector(".mh");
    if (!mh || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(reserve);
    ro.observe(mh);
    return () => ro.disconnect();
  }, [head, reserve]);

  // Read on each scroll event: one layout read, and the reducer hands back the same state (no
  // render) unless a line was crossed.
  useEffect(() => {
    const read = () => {
      const l = lines();
      if (l) dispatch({ type: "scroll", y: window.scrollY, lines: l });
    };
    read();
    window.addEventListener("scroll", read, { passive: true });
    window.addEventListener("resize", read);
    return () => {
      window.removeEventListener("scroll", read);
      window.removeEventListener("resize", read);
    };
  }, [lines]);

  const toggle = useCallback(() => {
    const l = lines();
    if (!l) return;
    let y = window.scrollY;
    // Folding near the top: bring the slim bar to the top of the window with the page right under
    // it, rather than leave the folded rows' space as a gap.
    if (!slim && y < l.expandAt) {
      y = Math.ceil(l.expandAt);
      window.scrollTo({ top: y, behavior: "instant" });
    }
    dispatch({ type: "toggle", y, lines: l });
  }, [lines, slim]);

  return { slim, toggle, anchor: setAnchor, head: setHead };
}
