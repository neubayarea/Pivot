// Live match state: a REST snapshot with envelopes folded in. Every step is idempotent (events
// by event_id, metrics by minute, pivots by pivot_id), so a frame applied twice, or applied after
// a snapshot that already holds it, changes nothing. Payload shapes: architecture §7.2.
import type { Envelope, Match, MatchEvent, MinuteMetric, Pivot1 as Pivot } from "@pivot/contracts";

export type LiveState = {
  match: Match;
  /** Oldest first, by MatchEvent.seq. */
  events: MatchEvent[];
  /** By minute. */
  metrics: MinuteMetric[];
  /** By minute; rejected ones are kept so a late pending frame cannot bring them back. */
  pivots: Pivot[];
};

/** `events` is everything after `lastEventSeq` of the previous state, or the whole list when `full`. */
export type Snapshot = { match: Match; events: MatchEvent[]; metrics: MinuteMetric[]; pivots: Pivot[]; full: boolean };

/** Highest MatchEvent.seq held, for `/events?since=`. */
export const lastEventSeq = (s: LiveState | null) => s?.events.at(-1)?.seq ?? -1;

export function applySnapshot(prev: LiveState | null, snap: Snapshot): LiveState {
  const keep = prev && !snap.full && prev.match.match_id === snap.match.match_id;
  const events = mergeEvents(keep ? prev.events : [], snap.events);
  return { match: snap.match, events, metrics: sortBy(snap.metrics, (m) => m.minute), pivots: sortBy(snap.pivots, (p) => p.minute) };
}

/** The pivot list again, refetched for another language or viewing mode. */
export const applyPivots = (s: LiveState, pivots: Pivot[]): LiveState => ({ ...s, pivots: sortBy(pivots, (p) => p.minute) });

/** One pivot refetched in the viewer's language after the feed pushed its English version. */
export function applyPivot(s: LiveState, pivot: Pivot): LiveState {
  if (pivot.match_id !== s.match.match_id) return s;
  // The checker can rule a pivot out while its translation is in flight; keep the ruling.
  if (s.pivots.some((x) => x.pivot_id === pivot.pivot_id && x.status === "rejected")) return s;
  return { ...s, pivots: upsert(s.pivots, pivot, (x) => x.minute, (x) => x.pivot_id) };
}

export function applyEnvelope(s: LiveState, env: Envelope): LiveState {
  if (env.match_id !== s.match.match_id) return s;
  const p = env.payload as Record<string, unknown>;
  switch (env.type) {
    case "match.status":
      return { ...s, match: applyStatus(s.match, p) };
    case "event.batch": {
      const batch = (Array.isArray(p.events) ? p.events : []) as MatchEvent[];
      return batch.length ? { ...s, events: mergeEvents(s.events, batch) } : s;
    }
    case "metric.updated": {
      if (typeof p.minute !== "number") return s;
      const old = s.metrics.find((m) => m.minute === p.minute);
      const metric = { ...EMPTY_METRIC, ...old, ...p, match_id: s.match.match_id } as MinuteMetric;
      return { ...s, metrics: upsert(s.metrics, metric, (m) => m.minute) };
    }
    case "pivot.pending": {
      const id = String(p.pivotId ?? p.pivot_id ?? "");
      if (!id || s.pivots.some((x) => x.pivot_id === id)) return s;
      const pending: Pivot = {
        pivot_id: id, match_id: s.match.match_id, minute: Number(p.minute ?? 0),
        direction: p.direction === "away" ? "away" : "home", status: "pending", severity: 1,
        narrative: null, chain_id: "", trigger_event_ids: [],
      };
      return { ...s, pivots: upsert(s.pivots, pending, (x) => x.minute, (x) => x.pivot_id) };
    }
    case "pivot.confirmed":
    case "pivot.degraded": {
      const pivot = p as unknown as Pivot;
      if (typeof pivot.pivot_id !== "string") return s;
      return { ...s, pivots: upsert(s.pivots, pivot, (x) => x.minute, (x) => x.pivot_id) };
    }
    case "pivot.rejected": {
      const id = String(p.pivotId ?? p.pivot_id ?? "");
      return { ...s, pivots: s.pivots.map((x) => (x.pivot_id === id ? { ...x, status: "rejected" } : x)) };
    }
    default:
      return s;
  }
}

const EMPTY_METRIC = { momentum: 0, pressure_home: 0, pressure_away: 0, threat_home: 0, threat_away: 0 };

function applyStatus(match: Match, p: Record<string, unknown>): Match {
  const next = { ...match };
  if (typeof p.status === "string") next.status = p.status as Match["status"];
  if (typeof p.speed === "number") next.speed = p.speed as Match["speed"];
  if (typeof p.period === "number") next.period = p.period as Match["period"];
  if (typeof p.clock === "number") next.clock = p.clock;
  else if (typeof p.minute === "number") next.clock = Math.max(match.clock, p.minute * 60);
  if (p.score && typeof p.score === "object") next.score = { ...match.score, ...(p.score as Partial<Match["score"]>) };
  return next;
}

function mergeEvents(have: MatchEvent[], add: MatchEvent[]): MatchEvent[] {
  if (!add.length) return have;
  const seen = new Set(have.map((e) => e.event_id));
  const fresh = add.filter((e) => !seen.has(e.event_id) && seen.add(e.event_id));
  if (!fresh.length) return have;
  const out = have.concat(fresh);
  // Batches normally arrive in order; only sort when one did not.
  const last = have.at(-1)?.seq ?? -1;
  return fresh.every((e, i) => e.seq > (i ? fresh[i - 1].seq : last)) ? out : sortBy(out, (e) => e.seq);
}

function sortBy<T>(xs: T[], key: (x: T) => number): T[] {
  return xs.slice().sort((a, b) => key(a) - key(b));
}

function upsert<T>(xs: T[], item: T, order: (x: T) => number, id: (x: T) => unknown = order): T[] {
  const k = id(item);
  return sortBy([...xs.filter((x) => id(x) !== k), item], order);
}
