// Fills useMatch() from the API: LiveSocket keeps the feed and decides when to reload over REST,
// LiveState folds both together, and this turns it into the MatchView the pages read.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { Match, Pivot1 as Pivot, TrackingFrame } from "@pivot/contracts";
import { clockLabel } from "../../fixtures/demo-1021";
import { ConnectionContext, MatchContext, computeStats, type Connection, type MatchView, type PivotDetail } from "../view";
import { api } from "./api";
import { LiveSocket, type ConnectionStatus } from "./socket";
import { applyEnvelope, applySnapshot, lastEventSeq, type LiveState } from "./state";

/** `?match=<id>`, else the API's most recent live match, else its most recent match. */
async function pickMatch(): Promise<string> {
  const asked = new URLSearchParams(window.location.search).get("match");
  if (asked) return asked;
  const matches = await api.listMatches();
  const pick = matches.find((m) => m.status === "live") ?? matches[0];
  if (!pick) throw new Error("no matches yet");
  return pick.match_id;
}

export default function LiveProvider({ children, fallback }: { children: ReactNode; fallback: ReactNode }) {
  const [state, setState] = useState<LiveState | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>({ state: "connecting", attempt: 0 });
  const stateRef = useRef<LiveState | null>(null);
  stateRef.current = state;
  const socketRef = useRef<LiveSocket | null>(null);

  useEffect(() => {
    let matchId: string | null = null;
    let alive = true;
    const socket = new LiveSocket({
      negotiate: async () => api.negotiate((matchId ??= await pickMatch())),
      resync: async (full) => {
        const id = matchId!;
        const since = full ? -1 : lastEventSeq(stateRef.current);
        const [match, events, metrics, pivots] = await Promise.all([
          api.getMatch(id), api.listEvents(id, since), api.getTimeline(id), api.listPivots(id),
        ]);
        if (alive) setState((prev) => applySnapshot(prev, { match, events, metrics, pivots, full }));
      },
      onEnvelope: (env) => alive && setState((prev) => (prev ? applyEnvelope(prev, env) : prev)),
      onStatus: (s) => alive && setStatus(s),
    });
    socketRef.current = socket;
    socket.start();
    return () => {
      alive = false;
      socket.stop();
    };
  }, []);

  const view = useMemo(() => (state ? toView(state) : null), [state]);
  const connection = useMemo<Connection>(
    () => ({ ...status, retryNow: () => socketRef.current?.retryNow() }),
    [status],
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
    playerName: (id) => (id ? (players.get(id) ?? id) : ""),
    eventById: (id) => byId.get(id),
    pivotDetail: (id) => {
      const pivot = shown.find((p) => p.pivot_id === id);
      return pivot && detailWithoutTracking(match, pivot);
    },
    playback: null,
  };
}

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
