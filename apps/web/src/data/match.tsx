// The one place S1 and S2 get match data from. By default it follows the live API and WebSocket
// feed (data/live); with `?fixture=1`, or VITE_PIVOT_FIXTURE=1 at build time, it replays the
// local demo-1021 fixture on a timer so the board can be shown without a backend; add
// `&degraded=1` to show every pivot as an automatic summary (the AI-down state). The fixture's
// explanations come in the viewer's language (fixtures/demo-1021-i18n). Pages call useMatch() either way.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { Match, Pivot1 as Pivot, Score } from "@pivot/contracts";
import { DEMO_1021, ROSTER, clockLabel, type MatchFixture } from "../fixtures/demo-1021";
import { localisePivot, localiseRowLabel } from "../fixtures/demo-1021-i18n";
import { useLang, type Lang } from "../i18n";
import LiveProvider from "./live/provider";
import { MatchContext, byShirt, computeStats, type MatchView, type Side, type Speed } from "./view";

export * from "./view";

/** True when the page should replay the fixture instead of following the API. */
export function fixtureMode(search = window.location.search): boolean {
  const q = new URLSearchParams(search).get("fixture");
  if (q !== null) return q !== "0";
  return import.meta.env.VITE_PIVOT_FIXTURE === "1";
}

const TICK_MS = 250;

// The fixture's ids end in the shirt number: "hcy-11" is Harbour City's number 11.
const FIXTURE_SQUADS = Object.fromEntries((["home", "away"] as Side[]).map((side) => [
  side,
  ROSTER[side].map(([player_id, name]) => ({ player_id, name, shirt: Number(player_id.split("-").pop()) || null })).sort(byShirt),
])) as MatchView["squads"];

/** What a pivot looks like when the Explainer timed out and the template wrote the summary. */
function degrade(p: Pivot): Pivot {
  if (p.status !== "confirmed") return p;
  return { ...p, status: "degraded", narrative: p.narrative && { ...p.narrative, source: "template" } };
}

function view(
  fx: MatchFixture, clock: number, playing: boolean, speed: Speed, degraded: boolean, lang: Lang,
): Omit<MatchView, "playback"> {
  const settled = (p: Pivot) => (degraded ? degrade(localisePivot(p, lang)) : localisePivot(p, lang));
  const shown = fx.events.filter((e) => e.t <= clock);
  const score: Score = { home: 0, away: 0, home_penalties: null, away_penalties: null };
  for (const e of shown) if (e.shot_outcome === "goal") score[e.team]++;
  const minute = clock / 60;
  const status: Match["status"] = clock >= fx.endAt ? "finished" : playing ? "live" : "paused";
  const pivots = fx.pivots
    .filter((p) => clock >= p.pendingAt)
    .map((p): Pivot =>
      clock >= p.confirmedAt ? settled(p.pivot) : { ...p.pivot, status: "pending", narrative: null })
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
    squads: FIXTURE_SQUADS,
    playerName: (id) => (id ? (fx.players[id] ?? id) : ""),
    eventById: (id) => fx.events.find((e) => e.event_id === id),
    pivotDetail: (id) => {
      const timeline = fx.pivots.find((p) => p.pivot.pivot_id === id);
      const detail = fx.details[id];
      if (!timeline || !detail) return undefined;
      const beforeAfter = detail.beforeAfter.map((r) => ({ ...r, label: localiseRowLabel(r.label, lang) }));
      return { ...detail, beforeAfter, pivot: settled(timeline.pivot) };
    },
  };
}

/** `?from=0` starts the replay at kick-off instead of just before the 74′ pivot. */
function startClock(fx: MatchFixture): number {
  const from = new URLSearchParams(window.location.search).get("from");
  const minute = from === null ? NaN : Number(from);
  return Number.isFinite(minute) ? Math.min(fx.endAt, Math.max(0, minute * 60)) : fx.startAt;
}

type ProviderProps = {
  children: ReactNode;
  /** Shown until the live feed has loaded its first state. */
  fallback?: ReactNode;
};

export function MatchProvider({ children, fallback = null }: ProviderProps) {
  // Decided once: in-app links drop `?fixture=1`, and the source must not switch under the pages.
  const [fixture] = useState(() => fixtureMode());
  return fixture ? (
    <FixtureProvider>{children}</FixtureProvider>
  ) : (
    <LiveProvider fallback={fallback}>{children}</LiveProvider>
  );
}

export function FixtureProvider({ children, fixture = DEMO_1021 }: { children: ReactNode; fixture?: MatchFixture }) {
  const [clock, setClock] = useState(() => startClock(fixture));
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState<Speed>(5);
  const [degraded] = useState(() => new URLSearchParams(window.location.search).get("degraded") === "1");
  const lang = useLang();

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
  const data = useMemo(
    () => view(fixture, second, playing, speed, degraded, lang),
    [fixture, second, playing, speed, degraded, lang],
  );
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
