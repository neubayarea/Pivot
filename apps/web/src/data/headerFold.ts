// The score header and what sticks at the top of the match page (Ax66, reworked in Ax77).
//
// The full header sits in the page and scrolls away like the rest of it. Right under it, a sticky
// block holds the slim score bar and the replay bar. That block is pulled up by the slim bar's
// height, so the slim bar lies over the header's last `SLIM_H` pixels; while the header is in view
// the slim bar is invisible. The block sticks at the moment those last pixels reach the top of the
// window, and that is when the slim bar shows, over exactly the part of the header it replaces.
// Nothing in the page changes size when it shows or hides, so the page never jumps and the scroll
// cannot argue with itself.
//
// The match tabs stick right under the block (`--pv-stick-h`) and a tab's own row of links under
// the tabs (`--pv-tabs-h`); see base.css. The root's scroll padding keeps anchors clear of all three.
//
// A press of either button pins that choice until the page is reloaded or another match opens:
// - "full": the whole header sticks at the top with the replay bar under it;
// - "slim": the header is gone and the slim bar sits (and sticks) in its place.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

/** Height of the slim bar (base.css `.mh.slim`, `.match-stick.auto`). */
export const SLIM_H = 48;

/** "auto" follows the scroll; "full" and "slim" were picked with the buttons. */
export type FoldMode = "auto" | "full" | "slim";

/** Whether the slim bar shows: picked, or the header has scrolled up to its last `SLIM_H` pixels. */
export const slimShown = (mode: FoldMode, stuck: boolean) => mode === "slim" || (mode === "auto" && stuck);

/** The header's bottom edge, measured from the top of the window: at `SLIM_H` or less, the bar takes over. */
export const isStuck = (headerBottom: number) => headerBottom <= SLIM_H + 0.5;

export type HeaderFold = {
  mode: FoldMode;
  /** In "auto": the header has scrolled past, so the slim bar shows. */
  stuck: boolean;
  expand: () => void;
  collapse: () => void;
  /** A zero-height marker where the header starts. */
  anchor: (el: HTMLDivElement | null) => void;
  /** The full header (`.mh`). */
  full: (el: HTMLElement | null) => void;
  /** The sticky block with the slim bar and the replay bar (`.match-stick`). */
  stick: (el: HTMLDivElement | null) => void;
};

const setVar = (name: string, px: number | null) => {
  const root = document.documentElement.style;
  if (px === null) root.removeProperty(name);
  else root.setProperty(name, `${Math.round(px)}px`);
};

/** Keeps `name` on the root set to the element's height while it is mounted (`--pv-tabs-h`, `--pv-sub-h`). */
export function useHeightVar(name: string) {
  const [el, setEl] = useState<HTMLElement | null>(null);
  useEffect(() => {
    if (!el) return;
    const write = () => setVar(name, el.getBoundingClientRect().height);
    write();
    const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(write);
    ro?.observe(el);
    return () => {
      ro?.disconnect();
      setVar(name, null);
    };
  }, [el, name]);
  return setEl;
}

/** The fold for one match; a new `matchId` lets the scroll decide again. */
export function useHeaderFold(matchId: string): HeaderFold {
  const [mode, setMode] = useState<FoldMode>("auto");
  const [stuck, setStuck] = useState(false);
  // Elements, not refs: the full header comes and goes with the mode.
  const [anchor, setAnchor] = useState<HTMLDivElement | null>(null);
  const [full, setFull] = useState<HTMLElement | null>(null);
  const [stick, setStick] = useState<HTMLDivElement | null>(null);

  useEffect(() => setMode("auto"), [matchId]);

  // One layout read per scroll event; React renders only when the bar should show or hide.
  useEffect(() => {
    if (!full) {
      setStuck(false);
      return;
    }
    const read = () => setStuck(isStuck(full.getBoundingClientRect().bottom));
    read();
    window.addEventListener("scroll", read, { passive: true });
    window.addEventListener("resize", read);
    // Also when something above the header changes height without a scroll (a banner, the first
    // visit's prompt, a page that loads already scrolled).
    const io = typeof IntersectionObserver === "undefined" ? null
      : new IntersectionObserver(read, { rootMargin: `-${SLIM_H}px 0px 0px 0px`, threshold: [0, 1] });
    io?.observe(full);
    return () => {
      io?.disconnect();
      window.removeEventListener("scroll", read);
      window.removeEventListener("resize", read);
    };
  }, [full]);

  // How tall the stuck stack is above the tabs, and where the block sticks under a pinned header.
  useEffect(() => {
    if (!stick) return;
    const write = () => {
      const fullH = mode === "full" && full ? full.getBoundingClientRect().height : 0;
      setVar("--mh-full-h", fullH);
      setVar("--pv-stick-h", fullH + stick.getBoundingClientRect().height);
    };
    write();
    const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(write);
    ro?.observe(stick);
    if (full) ro?.observe(full);
    return () => {
      ro?.disconnect();
      setVar("--mh-full-h", null);
      setVar("--pv-stick-h", null);
    };
  }, [stick, full, mode]);

  // A press that adds or removes the header while it is above the window would move the page under
  // the viewer's eyes; scroll by the same amount so what they were reading stays put. Near the top,
  // where the change is in view, the page simply follows it.
  const keep = useRef<number | null>(null);
  const page = () => document.querySelector<HTMLElement>("main.page");
  const pin = useCallback((next: FoldMode) => {
    const main = page();
    keep.current = anchor && main && anchor.getBoundingClientRect().top < 0 ? main.getBoundingClientRect().top : null;
    setMode(next);
  }, [anchor]);
  useLayoutEffect(() => {
    const before = keep.current;
    keep.current = null;
    const main = page();
    if (before === null || !main) return;
    const moved = main.getBoundingClientRect().top - before;
    if (Math.abs(moved) > 0.5) window.scrollBy({ top: moved, behavior: "instant" });
  }, [mode]);

  return {
    mode,
    stuck,
    expand: useCallback(() => pin("full"), [pin]),
    collapse: useCallback(() => pin("slim"), [pin]),
    anchor: setAnchor,
    full: setFull,
    stick: setStick,
  };
}
