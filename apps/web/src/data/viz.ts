// Data for the match pictures (Bx12): one small hook per component, each reading one read-only
// endpoint of apps/api/src/pivot_api/pictures.py. `upTo` (elapsed seconds) follows a replay or a
// live match; it is rounded down to `stepS` so a ticking clock does not send a request a second.
import { useCallback, useEffect, useMemo, useState } from "react";
import type { AveragePositionsReport, HeatmapReport, PassNetworkReport, ShotMap } from "@pivot/contracts";

export type VizOptions = {
  /** Only what happened by this elapsed second; the whole match when left out. */
  upTo?: number | null;
  /** One period: 1, 2, or extra time 3, 4. */
  period?: 1 | 2 | 3 | 4 | null;
  /** Round `upTo` down to this many seconds (default 30). */
  stepS?: number;
};

export type VizState<T> = {
  data: T | null; loading: boolean; error: boolean;
  /** Why it failed (Ax79): the HTTP status, no connection, or an answer that is not JSON. */
  fault?: number | "offline" | "data" | null;
  /** Asks again after a failure. */
  retry?: () => void;
};

/** `?up_to=&period=` plus any extra parameters, or "" with none. */
export function vizQuery(opts: VizOptions = {}, extra: Record<string, number> = {}): string {
  const q = new URLSearchParams();
  if (opts.upTo !== null && opts.upTo !== undefined) {
    const step = opts.stepS ?? 30;
    q.set("up_to", String(Math.floor(Math.max(0, opts.upTo) / step) * step));
  }
  if (opts.period) q.set("period", String(opts.period));
  for (const [k, v] of Object.entries(extra)) q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const vizPath = (matchId: string, what: "shots" | "heatmaps" | "pass-network" | "positions", query = "") =>
  `/api/matches/${encodeURIComponent(matchId)}/${what}${query}`;

/**
 * Answers already fetched, by path (Ax90, #430): the match page unmounts a tab when another opens,
 * so without this every switch asked the API again, and on the live match (`?up_to=`) each answer
 * takes the server a second or two. Kept for the last CACHE_MAX paths; a ticking clock moves to a new
 * path every `stepS`, so the old ones fall out. Failures are not kept.
 */
const CACHE_MAX = 80;
const answers = new Map<string, unknown>();
/** Requests on their way, so two parts of a page asking for the same path share one. */
const pending = new Map<string, Promise<unknown>>();

class HttpFault extends Error {
  constructor(readonly status: number, path: string) {
    super(`${path}: ${status}`);
  }
}

function remember(path: string, data: unknown) {
  answers.delete(path);
  answers.set(path, data);
  while (answers.size > CACHE_MAX) answers.delete(answers.keys().next().value as string);
}

/** GET `path` as JSON, once for everyone asking at the same time; kept after it succeeds. */
export function fetchCached<T>(path: string): Promise<T> {
  if (answers.has(path)) return Promise.resolve(answers.get(path) as T);
  let p = pending.get(path);
  if (!p) {
    p = fetch(path, { headers: { accept: "application/json" } })
      .then(async (r) => {
        if (!r.ok) throw new HttpFault(r.status, path);
        const data: unknown = await r.json();
        remember(path, data);
        return data;
      })
      .finally(() => pending.delete(path));
    pending.set(path, p);
  }
  return p as Promise<T>;
}

/** The kept answer for `path`, if there is one. */
export const cachedAnswer = <T>(path: string | null): T | undefined =>
  path !== null && answers.has(path) ? (answers.get(path) as T) : undefined;

/** Forget every kept answer (tests). */
export function clearVizCache() {
  answers.clear();
  pending.clear();
}

const ready = <T>(data: T): VizState<T> => ({ data, loading: false, error: false, fault: null });

/** GET a picture's data; null `path` (no match yet) fetches nothing. An answer fetched before shows at once. */
export function useVizData<T>(path: string | null): VizState<T> {
  const [state, setState] = useState<VizState<T>>(() => {
    const hit = cachedAnswer<T>(path);
    return hit !== undefined ? ready(hit) : { data: null, loading: path !== null, error: false, fault: null };
  });
  const [tries, setTries] = useState(0);
  useEffect(() => {
    if (path === null) return;
    const hit = cachedAnswer<T>(path);
    if (hit !== undefined) {
      setState((s) => (s.data === hit && !s.loading ? s : ready(hit)));
      return;
    }
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: false, fault: null }));
    fetchCached<T>(path)
      .then((data) => alive && setState(ready(data)))
      .catch((e: unknown) => {
        if (!alive) return;
        const fault = e instanceof HttpFault ? e.status : e instanceof TypeError ? "offline" : "data";
        setState({ data: null, loading: false, error: true, fault });
        if (import.meta.env.DEV) console.warn(e);
      });
    return () => {
      alive = false;
    };
  }, [path, tries]);
  const retry = useCallback(() => setTries((n) => n + 1), []);
  return useMemo(() => ({ ...state, retry }), [state, retry]);
}

export const useShotMap = (matchId: string | null, opts?: VizOptions) =>
  useVizData<ShotMap>(matchId ? vizPath(matchId, "shots", vizQuery(opts)) : null);

export const useHeatmaps = (matchId: string | null, opts?: VizOptions) =>
  useVizData<HeatmapReport>(matchId ? vizPath(matchId, "heatmaps", vizQuery(opts)) : null);

export const usePassNetwork = (matchId: string | null, opts?: VizOptions & { minPasses?: number }) =>
  useVizData<PassNetworkReport>(matchId ? vizPath(matchId, "pass-network",
    vizQuery(opts, opts?.minPasses ? { min_passes: opts.minPasses } : {})) : null);

export const useAveragePositions = (matchId: string | null, opts?: VizOptions) =>
  useVizData<AveragePositionsReport>(matchId ? vizPath(matchId, "positions", vizQuery(opts)) : null);
