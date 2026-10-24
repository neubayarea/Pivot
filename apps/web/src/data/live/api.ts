// REST client for the endpoints in apps/api/src/pivot_api/routes.py. Paths are relative, so the
// Vite dev server proxies them to the local API and a same-origin deploy needs nothing else.
import type { Match, MatchEvent, MinuteMetric, Pivot1 as Pivot } from "@pivot/contracts";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { headers: { accept: "application/json" }, ...init });
  if (!res.ok) throw new ApiError(res.status, `${init?.method ?? "GET"} /api${path}: ${res.status}`);
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
