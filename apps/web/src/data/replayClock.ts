// The replay clock the fixture and Start demo run on (Ax61). It is worked out from the wall clock
// since the last play, pause, seek or speed change, so `now()` can be read on every screen frame
// for the pitch, while the page's state only moves every TICK_MS. Ticking by a fixed step instead
// drifted with late timers, which made the pitch stop and go.
import { useCallback, useEffect, useRef, useState } from "react";
import type { Speed } from "./view";

const TICK_MS = 250;

const wall = () => (typeof performance !== "undefined" ? performance.now() : Date.now());

/** Where the clock is `ms` after an anchor, at `speed`, never past `end`. */
export const clockAfter = (from: number, ms: number, speed: number, end: number) =>
  Math.min(end, from + (Math.max(0, ms) * speed) / 1000);

export function useReplayClock(start: number, end: number, ready: boolean, initialSpeed: Speed) {
  const [clock, setClock] = useState(start);
  const [playing, setPlayingState] = useState(true);
  const [speed, setSpeedState] = useState<Speed>(initialSpeed);
  const anchor = useRef({ clock: start, at: wall() });
  const run = useRef({ playing, speed, end, ready });
  run.current = { playing, speed, end, ready };

  const now = useCallback(() => {
    const { playing, speed, end, ready } = run.current;
    const a = anchor.current;
    return playing && ready ? clockAfter(a.clock, wall() - a.at, speed, end) : Math.min(end, a.clock);
  }, []);
  const reanchor = (clock: number) => {
    anchor.current = { clock, at: wall() };
  };

  const seek = useCallback((t: number) => {
    const c = Math.min(run.current.end, Math.max(0, t));
    reanchor(c);
    setClock(c);
  }, []);
  const setPlaying = useCallback((on: boolean) => {
    reanchor(now());
    run.current = { ...run.current, playing: on };
    setPlayingState(on);
  }, [now]);
  const setSpeed = useCallback((s: Speed) => {
    reanchor(now());
    run.current = { ...run.current, speed: s };
    setSpeedState(s);
  }, [now]);

  useEffect(() => {
    if (!playing || !ready) return;
    // Starts from where the clock was held (while loading, or just set by play): no time has run yet.
    reanchor(anchor.current.clock);
    const timer = setInterval(() => setClock(now()), TICK_MS);
    return () => clearInterval(timer);
  }, [playing, ready, now]);

  useEffect(() => {
    if (clock >= end) setPlaying(false);
  }, [clock, end, setPlaying]);

  return { clock, playing, speed, now, seek, setPlaying, setSpeed };
}
