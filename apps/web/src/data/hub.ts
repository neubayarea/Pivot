// The match centre's data (C14, #354): `GET /api/hub` (apps/api/src/pivot_api/hub.py), refetched
// while the server is still generating its simulated matches, and the live match's clock, score
// and latest turning point worked out in the browser every second from the wall clock.
import { useEffect, useState } from "react";
import type { Score } from "@pivot/contracts";
import { minuteAt, minuteLabel, type PeriodStart } from "./clock";
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

/** A pre-match prediction (C14 PR 2): the fixture played 200 times from kick-off, nothing changed. */
export type HubPrediction = {
  n_runs: number;
  home_win: number;
  draw: number;
  away_win: number;
  ci95: Record<"home_win" | "draw" | "away_win", [number, number]>;
  scorelines: { home: number; away: number; share: number }[];
  xg: { home: number; away: number };
  goals: { home: number; away: number };
};

export type HubFixture = { match_id: string; home: HubTeam; away: HubTeam; venue: string; prediction: HubPrediction | null };

/** A round still to come (C15): its date (`2026-10-28`, the fictional calendar) and its fixtures. */
export type HubNext = { matchday: number; date?: string; fixtures: HubFixture[] };

/** A game of the season so far (#364): the score from the season file; `match_id` only when its full match is stored. */
export type HubPast = {
  home: HubTeam; away: HubTeam; score: Score; reds: { home: number; away: number }; match_id: string | null;
};

/** A round already played (#364), latest first. */
export type HubRound = { matchday: number; date?: string; results: HubPast[] };

export type HubData = {
  matches: HubLine[]; live: HubLive | null; generating: boolean; next: HubNext | null; schedule?: HubNext[];
  history?: HubRound[];
};

/** The viewer's club's games over the whole schedule, one line per round. */
export const clubGames = (rounds: HubNext[], club: string) =>
  rounds.flatMap((r) => r.fixtures.filter((f) => [f.home.short_name, f.away.short_name].includes(club))
    .map((f) => ({ round: r, fixture: f })));

/** The viewer's club's games first, the rest in the round's order. */
export const pinned = <T extends { home: HubTeam; away: HubTeam }>(items: T[], fav: string | null) =>
  fav ? [...items].sort((a, b) => Number(![a.home.short_name, a.away.short_name].includes(fav))
    - Number(![b.home.short_name, b.away.short_name].includes(fav))) : items;

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
/** `lastPivotLabel`: the clock minute the pivot card shows ("75", "45+2"), not the elapsed one. */
export type LiveNow = {
  clock: number; over: boolean; score: { home: number; away: number }; minute: string; lastPivot: number | null;
  lastPivotLabel: string | null;
};

export function liveNow(live: HubLive, nowMs = Date.now()): LiveNow {
  const clock = liveClock(live.length_s, nowMs);
  const over = clock >= live.length_s;
  const t = Math.min(clock, live.length_s);
  const score = { home: 0, away: 0 };
  for (const g of live.goals) if (g.t <= t) score[g.team]++;
  // A turning point shows once its minute is over, as on the replay (data/live/replay.tsx).
  const reached = live.pivot_minutes.filter((m) => t >= (m + 1) * 60);
  const last = reached.at(-1) ?? null;
  return {
    clock, over, score, minute: minuteAt(live.periods, t), lastPivot: last,
    lastPivotLabel: last === null ? null : minuteLabel(live.periods, last),
  };
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

/** A matchday's results with the same fixture played more than once (seed matches drawn onto the same
 * matchday, QA round 4) kept together, in the order they came. */
export function byFixture(lines: HubLine[]): HubLine[][] {
  const groups = new Map<string, HubLine[]>();
  for (const l of lines) {
    const key = `${l.home.short_name}-${l.away.short_name}`;
    groups.set(key, [...(groups.get(key) ?? []), l]);
  }
  return [...groups.values()];
}
