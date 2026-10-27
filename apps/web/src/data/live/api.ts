// REST client for the endpoints in apps/api/src/pivot_api/routes.py. Paths are relative, so the
// Vite dev server proxies them to the local API and a same-origin deploy needs nothing else.
import type {
  AgentTrace, Match, MatchEvent, MinuteMetric, OverlayFrame, OverlayTimeline, Pivot1 as Pivot, PlayerStatsReport, Scenario, ScenarioSpec,
  TrackingFrame, ViewerPrefs,
} from "@pivot/contracts";
import type { HubData } from "../hub";

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

/** `GET /api/sims`: the simulated matches the local API builds at startup (Ax6). */
export type SimsStatus = { total: number; ready: number; failed: number; generating: boolean; match_ids: string[] };

/** One chip in the What-if Lab, from `GET /api/pivots/{id}/scenarios` (A09; worker scenarios.py). */
export type ScenarioOption = {
  type: ScenarioSpec["type"];
  /** English, with the minute filled in: "Cancel 64′ substitution". */
  label: string;
  enabled: boolean;
  /** Why the chip is greyed out; null when it is enabled. */
  disabled_reason: string | null;
  target_event_id: string | null;
  /** Elapsed minute (0-based) the replay resumes from. */
  at_minute: number | null;
  team: "home" | "away" | null;
  /** move_substitution: `new_minute`, an elapsed minute (0-based). */
  params: Record<string, number | string>;
};

export type RunCount = ScenarioSpec["n_runs"];

/** `POST /api/scenarios`; the API fills the rest of the ScenarioSpec from the chip it matches. */
export type StartScenario = {
  pivot_id: string;
  type: ScenarioSpec["type"];
  n_runs?: RunCount;
  params?: Record<string, number | string>;
};

const m = (id: string) => `/matches/${encodeURIComponent(id)}`;

/** `?lang=&audience=&team=&player=` for the pivot endpoints (A11); team and player only when set. */
export function prefsQuery(p: ViewerPrefs): string {
  const q = new URLSearchParams({ lang: p.language, audience: p.audience });
  if (p.focus_team) q.set("team", p.focus_team);
  if (p.focus_player_id) q.set("player", p.focus_player_id);
  return `?${q}`;
}

/** A pivot as the API serves it with prefs: the Pivot plus the ViewerPrefs it actually used. */
type Served = Pivot & { prefs?: ViewerPrefs };

/**
 * Moves the served `prefs` (which says, say, "en" when a Chinese version could not be written)
 * onto the narrative, so the pages read the actual language from one place: narrative.prefs.
 */
export function withServedPrefs({ prefs, ...pivot }: Served, outer?: ViewerPrefs): Pivot {
  const used = prefs ?? outer;
  return used && pivot.narrative ? { ...pivot, narrative: { ...pivot.narrative, prefs: used } } : pivot;
}

/** The list answer is an array of pivots; also accept `{ pivots, prefs }` in case the API wraps it. */
function servedList(body: Served[] | { pivots: Served[]; prefs?: ViewerPrefs }): Pivot[] {
  return Array.isArray(body) ? body.map((p) => withServedPrefs(p)) : body.pivots.map((p) => withServedPrefs(p, body.prefs));
}

export const api = {
  listMatches: () => request<Match[]>("/matches"),
  getMatch: (id: string) => request<Match>(m(id)),
  sims: () => request<SimsStatus>("/sims"),
  /** The match centre (C14): the simulated live match and a line for every stored match (data/hub.ts). */
  hub: () => request<HubData>("/hub"),
  /** Events with seq > `since` (MatchEvent.seq, not the envelope seq), in seq order. */
  listEvents: (id: string, since = -1) => request<MatchEvent[]>(`${m(id)}/events?since=${since}`),
  getTimeline: (id: string) => request<MinuteMetric[]>(`${m(id)}/timeline`),
  /** Player and ball positions with from <= t <= to (elapsed seconds); 404 when the match has none (Ax9). */
  listFrames: (id: string, from: number, to: number) =>
    request<TrackingFrame[]>(`${m(id)}/frames?from=${from}&to=${to}`),
  listPivots: async (id: string, prefs?: ViewerPrefs) =>
    servedList(await request<Parameters<typeof servedList>[0]>(`${m(id)}/pivots${prefs ? prefsQuery(prefs) : ""}`)),
  getPivot: async (pivotId: string, prefs?: ViewerPrefs) =>
    withServedPrefs(await request<Served>(`/pivots/${encodeURIComponent(pivotId)}${prefs ? prefsQuery(prefs) : ""}`)),
  /** One player's numbers, events and pivots up to elapsed second `upTo` (the whole match when null); 404 without frames (#226). */
  playerStats: (id: string, player: string, upTo: number | null) =>
    request<PlayerStatsReport>(`${m(id)}/players/stats?player=${encodeURIComponent(player)}${upTo === null ? "" : `&up_to=${upTo}`}`),
  /** Score bug and card at elapsed second `clock`; the match's current clock when left out. */
  getOverlay: (id: string, clock?: number) =>
    request<OverlayFrame>(`${m(id)}/overlay${clock === undefined ? "" : `?clock=${clock}`}`),
  getOverlayTimeline: (id: string) => request<OverlayTimeline>(`${m(id)}/overlay/timeline`),
  /** The What-if chips for one pivot, disabled ones with their reason. */
  listScenarioOptions: (pivotId: string) => request<ScenarioOption[]>(`/pivots/${encodeURIComponent(pivotId)}/scenarios`),
  /** Queues a paired replay; 202 with the Scenario (queued, or completed when the API had it cached). */
  startScenario: (body: StartScenario) =>
    request<Scenario>("/scenarios", {
      method: "POST",
      headers: { accept: "application/json", "content-type": "application/json" },
      body: JSON.stringify(body),
    }),
  /** `lang` asks for the comparison in that language; the API writes it from the same result on first request. */
  getScenario: (scenarioId: string, lang?: ViewerPrefs["language"]) =>
    request<Scenario>(`/scenarios/${encodeURIComponent(scenarioId)}${lang ? `?lang=${lang}` : ""}`),
  /** Every agent step for one match, grouped by chain_id and in step order (Ax4). */
  listMatchTraces: (id: string) => request<AgentTrace[]>(`${m(id)}/traces`),
  /** The chains whose input_ref is this pivot id, a candidate the Judge turned down included; 404 when neither exists. */
  listPivotTraces: (pivotId: string) => request<AgentTrace[]>(`/pivots/${encodeURIComponent(pivotId)}/traces`),
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
