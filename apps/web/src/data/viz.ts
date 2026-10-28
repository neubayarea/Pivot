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

/** GET a picture's data; null `path` (no match yet) fetches nothing. */
export function useVizData<T>(path: string | null): VizState<T> {
  const [state, setState] = useState<VizState<T>>({ data: null, loading: path !== null, error: false, fault: null });
  const [tries, setTries] = useState(0);
  useEffect(() => {
    if (path === null) return;
    const ctl = new AbortController();
    setState((s) => ({ ...s, loading: true, error: false, fault: null }));
    let status: number | null = null;
    fetch(path, { headers: { accept: "application/json" }, signal: ctl.signal })
      .then(async (r) => {
        if (!r.ok) {
          status = r.status;
          throw new Error(`${path}: ${r.status}`);
        }
        setState({ data: (await r.json()) as T, loading: false, error: false, fault: null });
      })
      .catch((e: unknown) => {
        const fault = status ?? (e instanceof TypeError ? "offline" : "data");
        if (!ctl.signal.aborted) setState({ data: null, loading: false, error: true, fault });
        if (!ctl.signal.aborted && import.meta.env.DEV) console.warn(e);
      });
    return () => ctl.abort();
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
