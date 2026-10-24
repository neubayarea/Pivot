// The one place S1 and S2 get match data from. Today it replays the local demo-1021 fixture on a
// timer; C03 swaps the inside of MatchProvider for the API and WebSocket feed, and the
// pages keep calling useMatch() unchanged.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Match, MatchEvent, MinuteMetric, Pivot1 as Pivot, Score } from "@pivot/contracts";
import { DEMO_1021, clockLabel, type MatchFixture, type TeamInfo } from "../fixtures/demo-1021";
import type { PivotDetailData } from "../fixtures/pivot-detail";

export type Side = "home" | "away";
export type Speed = Match["speed"];
/** Everything S2 needs for one pivot. The pivot is the confirmed version even before the replay reaches it. */
export type PivotDetail = PivotDetailData & { pivot: Pivot };
export type TeamStats = { possession: number; shots: number; xg: number; pressures: number; finalThirdPasses: number };

export type MatchView = {
  match: Pick<Match, "match_id" | "clock" | "period" | "status" | "speed"> & { score: Score; clockLabel: string };
  teams: Record<Side, TeamInfo>;
  /** Visible events, newest first. */
  events: MatchEvent[];
  metrics: MinuteMetric[];
  /** Visible pivots, newest first; status flips from pending to confirmed on the fixture timeline. */
  pivots: Pivot[];
  stats: Record<Side, TeamStats>;
  playerName: (id: string | null) => string;
  eventById: (id: string) => MatchEvent | undefined;
  pivotDetail: (id: string) => PivotDetail | undefined;
  playback: {
    playing: boolean;
    setPlaying: (playing: boolean) => void;
    setSpeed: (speed: Speed) => void;
    restart: () => void;
  };
};

const TICK_MS = 250;
const MatchContext = createContext<MatchView | null>(null);

function computeStats(events: MatchEvent[]): Record<Side, TeamStats> {
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

function view(fx: MatchFixture, clock: number, playing: boolean, speed: Speed): Omit<MatchView, "playback"> {
  const shown = fx.events.filter((e) => e.t <= clock);
  const score: Score = { home: 0, away: 0, home_penalties: null, away_penalties: null };
  for (const e of shown) if (e.shot_outcome === "goal") score[e.team]++;
  const minute = clock / 60;
  const status: Match["status"] = clock >= fx.endAt ? "finished" : playing ? "live" : "paused";
  const pivots = fx.pivots
    .filter((p) => clock >= p.pendingAt)
    .map((p): Pivot =>
      clock >= p.confirmedAt ? p.pivot : { ...p.pivot, status: "pending", narrative: null })
    .reverse();
  return {
    match: {
      match_id: fx.matchId, clock, period: clock < 45 * 60 ? 1 : 2, status, speed, score,
      clockLabel: clockLabel(clock),
    },
    teams: fx.teams,
    events: shown.slice().reverse(),
    metrics: fx.metrics.filter((m) => m.minute <= minute),
    pivots,
    stats: computeStats(shown),
    playerName: (id) => (id ? (fx.players[id] ?? id) : ""),
    eventById: (id) => fx.events.find((e) => e.event_id === id),
    pivotDetail: (id) => {
      const timeline = fx.pivots.find((p) => p.pivot.pivot_id === id);
      const detail = fx.details[id];
      return timeline && detail ? { ...detail, pivot: timeline.pivot } : undefined;
    },
  };
}

/** `?from=0` starts the replay at kick-off instead of just before the 74′ pivot. */
function startClock(fx: MatchFixture): number {
  const from = new URLSearchParams(window.location.search).get("from");
  const minute = from === null ? NaN : Number(from);
  return Number.isFinite(minute) ? Math.min(fx.endAt, Math.max(0, minute * 60)) : fx.startAt;
}

export function MatchProvider({ children, fixture = DEMO_1021 }: { children: ReactNode; fixture?: MatchFixture }) {
  const [clock, setClock] = useState(() => startClock(fixture));
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState<Speed>(5);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setClock((c) => Math.min(fixture.endAt, c + (speed * TICK_MS) / 1000));
    }, TICK_MS);
    return () => clearInterval(id);
  }, [playing, speed, fixture]);

  useEffect(() => {
    if (clock >= fixture.endAt) setPlaying(false);
  }, [clock, fixture]);

  // Events and pivots only change on whole seconds, so recompute once per second of match time.
  const second = Math.floor(clock);
  const data = useMemo(() => view(fixture, second, playing, speed), [fixture, second, playing, speed]);
  const value = useMemo<MatchView>(
    () => ({
      ...data,
      playback: {
        playing,
        setPlaying,
        setSpeed,
        restart: () => {
          setClock(startClock(fixture));
          setPlaying(true);
        },
      },
    }),
    [data, playing, fixture],
  );

  return <MatchContext.Provider value={value}>{children}</MatchContext.Provider>;
}

export function useMatch(): MatchView {
  const ctx = useContext(MatchContext);
  if (!ctx) throw new Error("useMatch() must be used inside <MatchProvider>");
  return ctx;
}
