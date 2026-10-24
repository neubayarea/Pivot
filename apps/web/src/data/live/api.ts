// REST client for the endpoints in apps/api/src/pivot_api/routes.py. Paths are relative, so the
// Vite dev server proxies them to the local API and a same-origin deploy needs nothing else.
import type { Match, MatchEvent, MinuteMetric, OverlayFrame, OverlayTimeline, Pivot1 as Pivot } from "@pivot/contracts";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** False when something in front of the API answered (a proxy with the API stopped sends plain text). */
    readonly fromApi = true,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { headers: { accept: "application/json" }, ...init });
  if (!res.ok) {
    const fromApi = (res.headers.get("content-type") ?? "").includes("json");
    throw new ApiError(res.status, `${init?.method ?? "GET"} /api${path}: ${res.status}`, fromApi);
  }
  return (await res.json()) as T;
}

const m = (id: string) => `/matches/${encodeURIComponent(id)}`;

export const api = {
  listMatches: () => request<Match[]>("/matches"),
  getMatch: (id: string) => request<Match>(m(id)),
  /** Events with seq > `since` (MatchEvent.seq, not the envelope seq), in seq order. */
  listEvents: (id: string, since = -1) => request<MatchEvent[]>(`${m(id)}/events?since=${since}`),
  getTimeline: (id: string) => request<MinuteMetric[]>(`${m(id)}/timeline`),
  listPivots: (id: string) => request<Pivot[]>(`${m(id)}/pivots`),
  /** Score bug and card at elapsed second `clock`; the match's current clock when left out. */
  getOverlay: (id: string, clock?: number) =>
    request<OverlayFrame>(`${m(id)}/overlay${clock === undefined ? "" : `?clock=${clock}`}`),
  getOverlayTimeline: (id: string) => request<OverlayTimeline>(`${m(id)}/overlay/timeline`),
  /**
   * Start (or restart) the demo match. Not served yet: C06 calls it so the button works as soon
   * as the API adds it, and falls back to the fixture replay until then (see startDemo()).
   */
  startDemo: (matchId?: string) =>
    request<{ match_id: string }>("/dev/demo/start", {
      method: "POST",
      headers: { accept: "application/json", "content-type": "application/json" },
      body: JSON.stringify(matchId ? { match_id: matchId } : {}),
    }),
  /** The WebSocket URL for one match's feed. */
  negotiate: async (id: string) => {
    const { url } = await request<{ url: string }>(`/negotiate?match_id=${encodeURIComponent(id)}`, { method: "POST" });
    return sameOriginIfLoopback(url);
  },
};

/**
 * The local API answers negotiate with ws://127.0.0.1:8000/…, which bypasses the Vite proxy and
 * breaks when the page is served from another host. A loopback answer is rewritten onto the
 * page's own origin; anything else (Web PubSub) is used as given.
 */
export function sameOriginIfLoopback(url: string, page: Location = window.location): string {
  const u = new URL(url, page.href);
  if (!["127.0.0.1", "localhost", "[::1]"].includes(u.hostname)) return u.toString();
  return `${page.protocol === "https:" ? "wss:" : "ws:"}//${page.host}${u.pathname}${u.search}`;
}
