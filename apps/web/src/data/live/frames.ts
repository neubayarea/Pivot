// Tracking frames for the pitch board (C45), fetched five minutes at a time from
// GET /api/matches/{id}/frames (Ax9) so a whole match (~1 MB gzipped) is never one download.
// The window the clock is in comes first, then the next one, so playback does not wait.
import { useEffect, useRef, useState } from "react";
import type { TrackingFrame } from "@pivot/contracts";
import { ApiError, api } from "./api";

export const CHUNK_S = 300;

export const chunkOf = (t: number) => Math.floor(Math.max(0, t) / CHUNK_S);

/** The last frame at or before `t` (the first one if `t` is earlier); frames are in t order. */
export function frameAt(frames: TrackingFrame[], t: number): TrackingFrame | null {
  if (!frames.length) return null;
  let lo = 0;
  let hi = frames.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (frames[mid].t <= t) lo = mid;
    else hi = mid - 1;
  }
  return frames[lo];
}

export type Frames = {
  /** The frame to draw: at `t` once its window is in, else the last one drawn. */
  frame: TrackingFrame | null;
  /** The API has no frames for this match (the hand-made demo match, or no API at all). */
  missing: boolean;
};

/** Frames of one match around elapsed second `t`; `matchId` null fetches nothing (the fixture). */
export function useFrames(matchId: string | null, t: number): Frames {
  const [chunks, setChunks] = useState<Record<number, TrackingFrame[]>>({});
  const [missing, setMissing] = useState(matchId === null);
  const asked = useRef(new Set<number>());
  const shown = useRef<TrackingFrame | null>(null);
  const want = chunkOf(t);

  // Per mount, not per effect: a window still loading when the clock moves on is kept.
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    if (matchId === null || missing) return;
    for (const c of [want, want + 1]) {
      if (asked.current.has(c)) continue;
      asked.current.add(c);
      api.listFrames(matchId, c * CHUNK_S, (c + 1) * CHUNK_S - 1).then(
        (frames) => alive.current && setChunks((prev) => ({ ...prev, [c]: frames })),
        (err) => {
          asked.current.delete(c);           // asked again when the clock next moves into it
          if (alive.current && err instanceof ApiError && err.status === 404) setMissing(true);
        },
      );
    }
  }, [matchId, want, missing]);

  const here = chunks[want] ? frameAt(chunks[want], t) : null;
  if (here) shown.current = here;
  return { frame: here ?? shown.current, missing };
}
