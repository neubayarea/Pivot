// Fills useMatch() from the API: LiveSocket keeps the feed and decides when to reload over REST,
// LiveState folds both together, and this turns it into the MatchView the pages read.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { Match, Pivot1 as Pivot, TrackingFrame, ViewerPrefs } from "@pivot/contracts";
import { needsLocalised, usePrefs } from "../../i18n";
import { clockLabel } from "../../fixtures/demo-1021";
import {
  ConnectionContext, MatchContext, byShirt, computeStats, type Connection, type LoadProblem, type MatchView, type PivotDetail,
} from "../view";
import { ApiError, api } from "./api";
import { LiveSocket, type ConnectionStatus } from "./socket";
import { applyEnvelope, applyPivot, applyPivots, applySnapshot, lastEventSeq, type LiveState } from "./state";

class NoMatches extends Error {}

/** `?match=<id>` if the API has it, else its most recent live match, else its most recent match. */
async function pickMatch(): Promise<string> {
  const asked = new URLSearchParams(window.location.search).get("match");
  if (asked) return (await api.getMatch(asked)).match_id;
  const matches = await api.listMatches();
  const pick = matches.find((m) => m.status === "live") ?? matches[0];
  if (!pick) throw new NoMatches();
  return pick.match_id;
}

/** What went wrong before the first load. Anything but a network or 5xx failure needs the viewer, not a retry. */
export function classifyLoadError(err: unknown, asked: string | null): LoadProblem {
  if (err instanceof NoMatches) return { kind: "no-matches" };
  if (err instanceof ApiError) {
    if (err.status === 404 && asked) return { kind: "not-found", matchId: asked };
    // A proxy in front of a stopped API answers 502/503/504, or (Vite) a plain-text 500.
    if ([502, 503, 504].includes(err.status) || (err.status >= 500 && !err.fromApi)) return { kind: "unreachable" };
    return { kind: "server", status: err.status };
  }
  return { kind: "unreachable" };
}

/**
 * Pivots written for these prefs. A focus player the API does not know (saved while watching
 * another match) gets a 422; drop him rather than fail the load. TopBar clears the setting too.
 */
export async function listPivotsFor(id: string, prefs: ViewerPrefs): Promise<Pivot[]> {
  try {
    return await api.listPivots(id, prefs);
  } catch (err) {
    if (err instanceof ApiError && err.status === 422 && prefs.focus_player_id) {
      return api.listPivots(id, { ...prefs, focus_player_id: null });
    }
    throw err;
  }
}

const prefsKey = (p: ViewerPrefs) => `${p.language}|${p.audience}|${p.focus_team}|${p.focus_player_id}`;

export default function LiveProvider({ children, fallback }: { children: ReactNode; fallback: ReactNode }) {
  const [state, setState] = useState<LiveState | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>({ state: "connecting", attempt: 0 });
  const [problem, setProblem] = useState<LoadProblem | null>(null);
  const stateRef = useRef<LiveState | null>(null);
  stateRef.current = state;
  const socketRef = useRef<LiveSocket | null>(null);
  const matchIdRef = useRef<string | null>(null);
  const aliveRef = useRef(true);
  // Pivots are fetched in the viewer's language and mode; the feed pushes English analyst versions.
  const { prefs } = usePrefs();
  const prefsRef = useRef(prefs);
  prefsRef.current = prefs;
  const current = (asked: ViewerPrefs) => aliveRef.current && prefsKey(prefsRef.current) === prefsKey(asked);

  /** Refetch the pivot list for the current prefs; on failure the old list stays until the next resync. */
  const refreshPivots = useRef(() => {
    const id = matchIdRef.current;
    if (!id || !stateRef.current) return;
    const asked = prefsRef.current;
    listPivotsFor(id, asked).then(
      (pivots) => current(asked) && setState((prev) => (prev ? applyPivots(prev, pivots) : prev)),
      (err) => console.warn("Could not refetch pivots for", prefsKey(asked), err),
    );
  }).current;

  useEffect(() => {
    aliveRef.current = true;
    const alive = () => aliveRef.current;
    const socket = new LiveSocket({
      negotiate: async () => {
        try {
          const url = await api.negotiate((matchIdRef.current ??= await pickMatch()));
          if (alive()) setProblem(null);
          return url;
        } catch (err) {
          const p = classifyLoadError(err, new URLSearchParams(window.location.search).get("match"));
          if (alive()) setProblem(p);
          // Retrying will not make an unknown match appear; the socket keeps polling for everything else.
          if (p.kind === "not-found") socket.stop();
          throw err;
        }
      },
      resync: async (full) => {
        const id = matchIdRef.current!;
        const since = full ? -1 : lastEventSeq(stateRef.current);
        const asked = prefsRef.current;
        const [match, events, metrics, pivots] = await Promise.all([
          api.getMatch(id), api.listEvents(id, since), api.getTimeline(id), listPivotsFor(id, asked),
        ]);
        if (!alive()) return;
        setState((prev) => applySnapshot(prev, { match, events, metrics, pivots, full }));
        // The viewer switched language while this was loading: these pivots are in the old one.
        if (!current(asked)) refreshPivots();
      },
      onEnvelope: (env) => {
        if (!alive()) return;
        const asked = prefsRef.current;
        const id = (env.payload as { pivot_id?: unknown } | null)?.pivot_id;
        const settled = env.type === "pivot.confirmed" || env.type === "pivot.degraded";
        if (settled && typeof id === "string" && needsLocalised(asked)) {
          // Hold the English version back while the viewer's own one loads; show it if that fails.
          api.getPivot(id, asked).then(
            (pivot) => current(asked) && setState((prev) => (prev ? applyPivot(prev, pivot) : prev)),
            () => alive() && setState((prev) => (prev ? applyEnvelope(prev, env) : prev)),
          );
          return;
        }
        setState((prev) => (prev ? applyEnvelope(prev, env) : prev));
      },
      onStatus: (s) => alive() && setStatus(s),
    });
    socketRef.current = socket;
    socket.start();
    return () => {
      aliveRef.current = false;
      socket.stop();
    };
  }, []);

  // A new language or viewing mode: fetch the pivots again (the first load already used it).
  const key = prefsKey(prefs);
  const loadedKey = useRef(key);
  useEffect(() => {
    if (loadedKey.current === key) return;
    loadedKey.current = key;
    refreshPivots();
  }, [key, refreshPivots]);

  const view = useMemo(() => (state ? toView(state) : null), [state]);
  const connection = useMemo<Connection>(
    () => ({ ...status, problem, retryNow: () => socketRef.current?.retryNow() }),
    [status, problem],
  );

  return (
    <ConnectionContext.Provider value={connection}>
      {view ? <MatchContext.Provider value={view}>{children}</MatchContext.Provider> : fallback}
    </ConnectionContext.Provider>
  );
}

function toView({ match, events, metrics, pivots }: LiveState): MatchView {
  const players = new Map<string, string>();
  for (const team of [match.home, match.away]) for (const p of team.squad) players.set(p.player_id, p.name);
  const byId = new Map(events.map((e) => [e.event_id, e]));
  const shown = pivots.filter((p) => p.status !== "rejected");
  return {
    match: {
      match_id: match.match_id, clock: match.clock, period: match.period, status: match.status,
      speed: match.speed, score: match.score, clockLabel: clockLabel(match.clock),
    },
    teams: { home: teamInfo(match.home), away: teamInfo(match.away) },
    events: events.slice().reverse(),
    metrics,
    pivots: shown.slice().reverse(),
    stats: computeStats(events),
    squads: {
      home: match.home.squad.map(squadPlayer).sort(byShirt),
      away: match.away.squad.map(squadPlayer).sort(byShirt),
    },
    playerName: (id) => (id ? (players.get(id) ?? id) : ""),
    eventById: (id) => byId.get(id),
    pivotDetail: (id) => {
      const pivot = shown.find((p) => p.pivot_id === id);
      return pivot && detailWithoutTracking(match, pivot);
    },
    playback: null,
  };
}

const squadPlayer = ({ player_id, name, shirt_number }: Match["home"]["squad"][number]) =>
  ({ player_id, name, shirt: shirt_number ?? null });

const teamInfo = ({ name, short_name, side, color }: Match["home"]) => ({ name, short_name, side, color });

/**
 * The API serves no tracking frames or before/after table yet, so S2 gets an empty pitch over
 * the two minutes either side of the pivot; evidence events still draw where they happened.
 */
function detailWithoutTracking(match: Match, pivot: Pivot): PivotDetail {
  const from = Math.max(0, (pivot.minute - 2) * 60);
  const frame: TrackingFrame = {
    match_id: match.match_id, period: match.period, t: from, possession: null, players: [],
    ball: { owner_id: null, x: 52.5, y: 34, z: 0 },
  };
  return { pivot, window: [from, (pivot.minute + 2) * 60], frames: [frame], beforeAfter: [] };
}
