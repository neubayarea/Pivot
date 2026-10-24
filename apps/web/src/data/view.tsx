// What S1 and S2 read, whichever source fills it: the live API (data/live) or the fixture replay.
import { createContext, useContext } from "react";
import type { Match, MatchEvent, MinuteMetric, Pivot1 as Pivot, Score } from "@pivot/contracts";
import type { TeamInfo } from "../fixtures/demo-1021";
import type { PivotDetailData } from "../fixtures/pivot-detail";
import type { ConnectionStatus } from "./live/socket";

export type Side = "home" | "away";
export type Speed = Match["speed"];
/** Everything S2 needs for one pivot. The pivot is the confirmed version even before the replay reaches it. */
export type PivotDetail = PivotDetailData & { pivot: Pivot };
/** One player in the focus-player picker. */
export type SquadPlayer = { player_id: string; name: string; shirt: number | null };
export type TeamStats = { possession: number; shots: number; xg: number; pressures: number; finalThirdPasses: number };

export type MatchView = {
  match: Pick<Match, "match_id" | "clock" | "period" | "status" | "speed"> & { score: Score; clockLabel: string };
  teams: Record<Side, TeamInfo>;
  /** Visible events, newest first. */
  events: MatchEvent[];
  metrics: MinuteMetric[];
  /** Visible pivots, newest first. */
  pivots: Pivot[];
  stats: Record<Side, TeamStats>;
  /** Both squads, for the focus-player picker; ordered by shirt number. */
  squads: Record<Side, SquadPlayer[]>;
  playerName: (id: string | null) => string;
  eventById: (id: string) => MatchEvent | undefined;
  pivotDetail: (id: string) => PivotDetail | undefined;
  /** Replay controls; only the fixture and a replay of a stored match (Start demo) have them. */
  playback: {
    playing: boolean;
    setPlaying: (playing: boolean) => void;
    setSpeed: (speed: Speed) => void;
    restart: () => void;
    /** Move the replay clock to elapsed second `t` (the pitch board's scrubber). */
    seek: (t: number) => void;
    /** Where the replay stops, in elapsed seconds. */
    end: number;
  } | null;
};

/** Why the live feed has no match to show yet; StartupScreen turns it into a message and a next step. */
export type LoadProblem =
  | { kind: "no-matches" }
  | { kind: "not-found"; matchId: string }
  | { kind: "unreachable" }
  | { kind: "server"; status: number };

/** The live feed's state; null when the page runs on the fixture. */
export type Connection = ConnectionStatus & { retryNow: () => void; problem: LoadProblem | null };

export const MatchContext = createContext<MatchView | null>(null);
export const ConnectionContext = createContext<Connection | null>(null);

export function useMatch(): MatchView {
  const ctx = useContext(MatchContext);
  if (!ctx) throw new Error("useMatch() must be used inside <MatchProvider>");
  return ctx;
}

/** The match view if there is one yet; the live feed has none until its first REST load. */
export const useMaybeMatch = () => useContext(MatchContext);

export const useConnection = () => useContext(ConnectionContext);

/** Shirt order, players without a number last. */
export const byShirt = (a: SquadPlayer, b: SquadPlayer) => (a.shirt ?? 999) - (b.shirt ?? 999) || a.name.localeCompare(b.name);

/** True when the player made or received the action, or came on or went off in it. */
export const involves = (e: Pick<MatchEvent, "player_id" | "receiver_id" | "substitution">, playerId: string | null) =>
  playerId !== null && [e.player_id, e.receiver_id, e.substitution?.player_on_id, e.substitution?.player_off_id].includes(playerId);

export function computeStats(events: MatchEvent[]): Record<Side, TeamStats> {
  const s = {
    home: { possession: 0, shots: 0, xg: 0, pressures: 0, finalThirdPasses: 0 },
    away: { possession: 0, shots: 0, xg: 0, pressures: 0, finalThirdPasses: 0 },
  };
  for (const e of events) {
    const t = s[e.team];
    if (e.type === "pass") {
      t.possession++;
      if (e.third === "final") t.finalThirdPasses++;
    } else if (e.type === "shot") {
      t.shots++;
      t.xg += e.xg ?? 0;
    } else if (e.type === "pressure") t.pressures++;
  }
  const passes = s.home.possession + s.away.possession || 1;
  s.home.possession = Math.round((s.home.possession / passes) * 100);
  s.away.possession = 100 - s.home.possession;
  return s;
}
