// "Start demo" on a stored match (Ax9): loads the whole match over REST once, then plays it back on
// a clock in the browser, the way the fixture replay does. Events, the momentum curve and pivots
// appear as the clock reaches them; nothing on the server changes, so it works on any deploy.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { Match, MatchEvent, Pivot1 as Pivot, Score } from "@pivot/contracts";
import { needsLocalised, usePrefs } from "../../i18n";
import { useReplayClock } from "../replayClock";
import { ConnectionContext, LocalisingContext, MatchContext, type Connection, type MatchView } from "../view";
import type { MatchChoice } from "../choice";
import { api } from "./api";
import { classifyLoadError, firstPivots, listPivotsFor, pickMatch, toView } from "./provider";
import type { LiveState } from "./state";

/** A pivot shows as "pending" once its minute is over, and settles this many seconds later (as the worker would). */
const SETTLE_S = 40;

/** `?from=` (minutes) asks for a replay of the chosen match from there; null when the link has none. */
export function replayStart(search: string): number | null {
  const from = new URLSearchParams(search).get("from");
  const minute = from === null || from === "" ? NaN : Number(from);
  return Number.isFinite(minute) ? Math.max(0, minute * 60) : null;
}

/** Where the replay stops: the final clock of a finished match, else its last event. */
export const replayEnd = ({ match, events }: LiveState) =>
  Math.max(match.status === "finished" ? match.clock : 0, events.at(-1)?.t ?? 0);

const goals = (events: MatchEvent[]): Score => {
  const score: Score = { home: 0, away: 0, home_penalties: null, away_penalties: null };
  for (const e of events) if (e.type === "shot" && e.shot_outcome === "goal") score[e.team]++;
  return score;
};

/** The match as it stood at `clock`: what happened by then, and pivots in the state they would have had. */
export function stateAt(full: LiveState, clock: number, playing: boolean): LiveState {
  const end = replayEnd(full);
  const events = full.events.filter((e) => e.t <= clock);
  const minute = clock / 60;
  const pivots = full.pivots
    .filter((p) => p.status !== "rejected" && clock >= (p.minute + 1) * 60)
    .map((p): Pivot => (clock >= (p.minute + 1) * 60 + SETTLE_S ? p : { ...p, status: "pending", narrative: null }));
  const second = full.match.periods.filter((p) => p.period > 1 && clock >= p.start_t).at(-1);
  const match: Match = {
    ...full.match,
    clock,
    period: second?.period ?? 1,
    status: clock >= end ? "finished" : playing ? "live" : "paused",
    score: clock >= end ? full.match.score : goals(events),
  };
  return { match, events, metrics: full.metrics.filter((m) => m.minute <= minute), pivots };
}

type Props = { children: ReactNode; fallback: ReactNode; choice: MatchChoice; from: number; onMissing?: (id: string) => void };

export default function ReplayProvider({ children, fallback, choice, from, onMissing }: Props) {
  const [full, setFull] = useState<LiveState | null>(null);
  const [connection, setConnection] = useState<Connection | null>(null);
  const { prefs } = usePrefs();
  const prefsRef = useRef(prefs);
  prefsRef.current = prefs;
  const matchId = useRef<string | null>(null);
  const [localising, setLocalising] = useState(false);

  /** The pivots again in the viewer's language and mode; on failure the old ones stay. */
  const localise = useRef((isAlive: () => boolean) => {
    const id = matchId.current;
    if (!id) return;
    const asked = prefsRef.current;
    const current = () => isAlive() && prefsRef.current === asked;
    setLocalising(true);
    listPivotsFor(id, asked).then(
      (pivots) => current() && setFull((prev) => (prev ? { ...prev, pivots } : prev)),
      (err) => console.warn("Could not refetch pivots for", asked, err),
    ).finally(() => current() && setLocalising(false));
  }).current;

  useEffect(() => {
    let alive = true;
    (async () => {
      const picked = await pickMatch(choice);
      const id = (matchId.current = picked.id);
      if (picked.missing && alive) onMissing?.(picked.missing);
      const asked = prefsRef.current;
      const [match, events, metrics, pivots] = await Promise.all([
        api.getMatch(id), api.listEvents(id), api.getTimeline(id), firstPivots(id, asked),
      ]);
      if (!alive) return;
      setFull({ match, events, metrics, pivots });
      // Opened on the English pivots (see firstPivots), or the viewer switched while this loaded.
      if (needsLocalised(asked) || prefsRef.current !== asked) localise(() => alive);
    })().catch((err) => {
      if (!alive) return;
      setConnection({
        state: "failed", attempt: 0, problem: classifyLoadError(err, choice.fromUrl ? choice.id : null),
        retryNow: () => window.location.reload(),
      });
    });
    return () => {
      alive = false;
    };
  }, []);

  // A new language or viewing mode refetches the pivots only.
  const key = `${prefs.language}|${prefs.audience}|${prefs.focus_team}|${prefs.focus_player_id}`;
  const loadedKey = useRef(key);
  useEffect(() => {
    if (loadedKey.current === key || !matchId.current) return;
    loadedKey.current = key;
    let alive = true;
    localise(() => alive);
    return () => {
      alive = false;
    };
  }, [key, localise]);

  const end = full ? replayEnd(full) : Infinity;
  const { clock, playing, speed, now, seek, setPlaying, setSpeed } = useReplayClock(from, end, !!full, 20);

  // Like the fixture: events and pivots only change on whole seconds.
  const second = Math.floor(clock);
  const data = useMemo(() => (full ? toView(stateAt(full, second, playing)) : null), [full, second, playing]);
  const view = useMemo<MatchView | null>(() => data && {
    ...data,
    match: { ...data.match, speed },
    playback: {
      playing,
      setPlaying,
      setSpeed,
      restart: () => {
        seek(from);
        setPlaying(true);
      },
      seek,
      end,
      now,
    },
  }, [data, playing, speed, from, end, seek, setPlaying, setSpeed, now]);

  return (
    <ConnectionContext.Provider value={connection}>
      <LocalisingContext.Provider value={localising}>
        {view ? <MatchContext.Provider value={view}>{children}</MatchContext.Provider> : fallback}
      </LocalisingContext.Provider>
    </ConnectionContext.Provider>
  );
}
