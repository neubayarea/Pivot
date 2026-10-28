// Tracking frames for the pitch board (C45), fetched five minutes at a time from
// GET /api/matches/{id}/frames (Ax9) so a whole match (~1 MB gzipped) is never one download.
// The window the clock is in comes first, then the next one, so playback does not wait.
import { useCallback, useEffect, useRef, useState } from "react";
import type { TrackingFrame } from "@pivot/contracts";
import { indexAt } from "../motion";
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

export type FrameWindow = {
  /** The frames, null while loading or after a failure. */
  frames: TrackingFrame[] | null;
  /** Why the last request failed (not a 404: that is no frames), or null. */
  error: unknown;
  /** Asks again after a failure. */
  retry: () => void;
};

/** Every frame in [from, to], fetched once per window, with the failure and a retry (Ax79). */
export function useFrameWindowState(matchId: string | null, from: number, to: number): FrameWindow {
  const [got, setGot] = useState<{ key: string; frames: TrackingFrame[] | null; error: unknown } | null>(null);
  const [tries, setTries] = useState(0);
  const key = `${matchId}:${from}:${to}`;
  useEffect(() => {
    if (matchId === null || to < 0) return;
    let live = true;
    api.listFrames(matchId, Math.max(0, from), to).then(
      (frames) => live && setGot({ key, frames, error: null }),
      (err) => live && setGot(err instanceof ApiError && err.status === 404 ? { key, frames: [], error: null } : { key, frames: null, error: err }),
    );
    return () => {
      live = false;
    };
  }, [matchId, from, to, key, tries]);
  const mine = got?.key === key ? got : null;
  const retry = useCallback(() => {
    setGot(null);
    setTries((n) => n + 1);
  }, []);
  return { frames: mine?.frames ?? null, error: mine?.error ?? null, retry };
}

/** Every frame in [from, to], fetched once per window (Ax36's "before" shape); null while loading, empty when it failed. */
export function useFrameWindow(matchId: string | null, from: number, to: number): TrackingFrame[] | null {
  const { frames, error } = useFrameWindowState(matchId, from, to);
  return error ? [] : frames;
}

export type FrameStore = {
  /** The loaded frames around elapsed second `t` (two either side, across window edges); empty until its window is in. */
  around: (t: number) => TrackingFrame[];
  /** The API has no frames for this match. */
  missing: boolean;
  /** Goes up each time a window arrives, so whatever reads `around` can draw again. */
  version: number;
  /** Why the window the clock is in could not be loaded (not a 404), or null. */
  error: unknown;
  /** Asks for the failed window again. */
  retry: () => void;
};

/**
 * Frames for a pitch that is redrawn on every screen frame (Ax61): the windows are kept outside
 * React state, so reading them costs nothing, and the one before and the one after the clock are
 * fetched too, so playing on or scrubbing back does not wait for the network.
 */
export function useFrameStore(matchId: string | null, t: number): FrameStore {
  const chunks = useRef(new Map<number, TrackingFrame[]>());
  const asked = useRef(new Set<number>());
  const [version, setVersion] = useState(0);
  const [missing, setMissing] = useState(matchId === null);
  const [error, setError] = useState<unknown>(null);
  const [tries, setTries] = useState(0);
  const want = chunkOf(t);

  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    if (matchId === null || missing) return;
    // The window the clock is in first, then the next and the one before.
    for (const c of [want, want + 1, want - 1]) {
      if (c < 0 || asked.current.has(c)) continue;
      asked.current.add(c);
      api.listFrames(matchId, c * CHUNK_S, (c + 1) * CHUNK_S - 1).then(
        (frames) => {
          if (!alive.current) return;
          chunks.current.set(c, frames);
          if (c === want) setError(null);
          setVersion((v) => v + 1);
        },
        (err) => {
          asked.current.delete(c);
          if (!alive.current || c !== want) return;
          if (err instanceof ApiError && err.status === 404) setMissing(true);
          else setError(err);
        },
      );
    }
  }, [matchId, want, missing, tries]);

  const around = useCallback((at: number) => framesAround(chunks.current, at), []);
  const retry = useCallback(() => {
    setError(null);
    setTries((n) => n + 1);
  }, []);
  return { around, missing, version, error, retry };
}

/** Up to two frames either side of `t` from the loaded windows; empty if the window `t` is in is not loaded. */
export function framesAround(chunks: ReadonlyMap<number, TrackingFrame[]>, t: number): TrackingFrame[] {
  const c = chunkOf(t);
  const here = chunks.get(c);
  if (!here?.length) return [];
  const i = indexAt(here, t);
  const out = here.slice(Math.max(0, i - 2), i + 3);
  if (i < 2) out.unshift(...(chunks.get(c - 1)?.slice(-(2 - i)) ?? []));
  if (i + 3 > here.length) out.push(...(chunks.get(c + 1)?.slice(0, i + 3 - here.length) ?? []));
  return out;
}
