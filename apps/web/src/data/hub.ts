// The match centre's data (C14, #354): `GET /api/hub` (apps/api/src/pivot_api/hub.py), refetched
// while the server is still generating its simulated matches, and the live match's clock, score
// and latest turning point worked out in the browser every second from the wall clock.
import { useEffect, useState } from "react";
import type { Score } from "@pivot/contracts";
import { minuteAt, type PeriodStart } from "./clock";
import { api } from "./live/api";
import { liveClock } from "./liveClock";

export type HubTeam = { name: string; short_name: string; color: string };

export type HubLine = {
  match_id: string;
  matchday: number | null;
  status: "scheduled" | "live" | "paused" | "finished";
  home: HubTeam;
  away: HubTeam;
  score: Score;
  length_s: number;
  periods: PeriodStart[];
  pivots: number;
  best: { player_id: string; name: string; team: "home" | "away"; rating: number } | null;
  live: boolean;
};

export type HubLive = {
  match_id: string;
  length_s: number;
  periods: PeriodStart[];
  goals: { t: number; team: "home" | "away" }[];
  pivot_minutes: number[];
};

export type HubData = { matches: HubLine[]; live: HubLive | null; generating: boolean };

export type HubState = { data: HubData | null; failed: boolean };

const POLL_MS = 3000;

export function useHub(): HubState {
  const [state, setState] = useState<HubState>({ data: null, failed: false });
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      const data = await api.hub().catch(() => null);
      if (!alive) return;
      setState((prev) => ({ data: data ?? prev.data, failed: data === null && prev.data === null }));
      if (data === null || data.generating) timer = setTimeout(load, POLL_MS);
    };
    load();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, []);
  return state;
}

/** The live match right now: its clock, score, minute label and the latest turning point it has reached. */
export type LiveNow = { clock: number; over: boolean; score: { home: number; away: number }; minute: string; lastPivot: number | null };

export function liveNow(live: HubLive, nowMs = Date.now()): LiveNow {
  const clock = liveClock(live.length_s, nowMs);
  const over = clock >= live.length_s;
  const t = Math.min(clock, live.length_s);
  const score = { home: 0, away: 0 };
  for (const g of live.goals) if (g.t <= t) score[g.team]++;
  // A turning point shows once its minute is over, as on the replay (data/live/replay.tsx).
  const reached = live.pivot_minutes.filter((m) => t >= (m + 1) * 60);
  return { clock, over, score, minute: minuteAt(live.periods, t), lastPivot: reached.at(-1) ?? null };
}

/** Ticks once a second, so the live card's clock moves. */
export function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(timer);
  }, [ms]);
  return now;
}

/** Results grouped by matchday, latest first; matches without one come last. */
export function byMatchday(lines: HubLine[]): [number | null, HubLine[]][] {
  const groups = new Map<number | null, HubLine[]>();
  for (const l of lines) groups.set(l.matchday, [...(groups.get(l.matchday) ?? []), l]);
  return [...groups].sort(([a], [b]) => (a === null ? 1 : b === null ? -1 : b - a));
}
