import { describe, expect, it } from "vitest";
import type { Envelope, Match, MatchEvent, Pivot1 as Pivot } from "@pivot/contracts";
import { sameOriginIfLoopback } from "./api";
import { applyEnvelope, applySnapshot, lastEventSeq, type LiveState } from "./state";

const match = {
  match_id: "m1", clock: 600, period: 1, status: "live", speed: 5,
  score: { home: 0, away: 0, home_penalties: null, away_penalties: null },
} as Match;
const ev = (seq: number) => ({ event_id: `e${seq}`, seq, t: seq * 10, team: "home", type: "pass" }) as MatchEvent;
const pivot = (minute: number, status: Pivot["status"] = "confirmed") =>
  ({ pivot_id: `m1:p${minute}`, match_id: "m1", minute, status, direction: "home", severity: 2 }) as Pivot;
const env = (type: Envelope["type"], payload: Record<string, unknown>, match_id = "m1"): Envelope =>
  ({ type, match_id, seq: 0, ts: "", payload });

const base = (): LiveState =>
  applySnapshot(null, { match, events: [ev(1), ev(2)], metrics: [], pivots: [], full: true });

describe("live state", () => {
  it("adds only new events from a gap reload, and replaces them on a full one", () => {
    const s = base();
    expect(lastEventSeq(s)).toBe(2);
    const gap = applySnapshot(s, { match, events: [ev(2), ev(3)], metrics: [], pivots: [], full: false });
    expect(gap.events.map((e) => e.seq)).toEqual([1, 2, 3]);
    const full = applySnapshot(gap, { match, events: [ev(1)], metrics: [], pivots: [], full: true });
    expect(full.events.map((e) => e.seq)).toEqual([1]);
  });

  it("folds envelopes in idempotently", () => {
    let s = base();
    const batch = env("event.batch", { events: [ev(4), ev(3)] });
    s = applyEnvelope(applyEnvelope(s, batch), batch);
    expect(s.events.map((e) => e.seq)).toEqual([1, 2, 3, 4]);

    const metric = env("metric.updated", { minute: 10, momentum: 0.4, pressure_home: 0.6, pressure_away: 0.2 });
    s = applyEnvelope(applyEnvelope(s, metric), metric);
    expect(s.metrics).toEqual([expect.objectContaining({ minute: 10, momentum: 0.4, match_id: "m1", threat_home: 0 })]);

    s = applyEnvelope(s, env("match.status", { status: "paused", minute: 11, score: { home: 1, away: 0 } }));
    expect(s.match).toMatchObject({ status: "paused", clock: 660, score: { home: 1, away: 0, home_penalties: null } });
  });

  it("moves a pivot from pending to confirmed and hides nothing it should not", () => {
    let s = applyEnvelope(base(), env("pivot.pending", { pivotId: "m1:p74", minute: 74, direction: "away" }));
    expect(s.pivots).toEqual([expect.objectContaining({ pivot_id: "m1:p74", status: "pending", direction: "away" })]);
    s = applyEnvelope(s, env("pivot.confirmed", { ...pivot(74) }));
    expect(s.pivots).toEqual([expect.objectContaining({ status: "confirmed" })]);
    // A late pending frame does not undo the confirmation.
    s = applyEnvelope(s, env("pivot.pending", { pivotId: "m1:p74", minute: 74 }));
    expect(s.pivots[0].status).toBe("confirmed");
    s = applyEnvelope(s, env("pivot.rejected", { pivotId: "m1:p74" }));
    expect(s.pivots[0].status).toBe("rejected");
  });

  it("ignores frames for another match", () => {
    const s = base();
    expect(applyEnvelope(s, env("event.batch", { events: [ev(9)] }, "m2"))).toBe(s);
  });
});

describe("sameOriginIfLoopback", () => {
  const page = { href: "http://localhost:5173/", protocol: "http:", host: "localhost:5173" } as Location;

  it("routes the local API's loopback URL through the page's origin", () => {
    expect(sameOriginIfLoopback("ws://127.0.0.1:8000/api/ws/matches/m1", page)).toBe("ws://localhost:5173/api/ws/matches/m1");
    const https = { href: "https://pivot.example/", protocol: "https:", host: "pivot.example" } as Location;
    expect(sameOriginIfLoopback("ws://127.0.0.1:8000/api/ws/matches/m1", https)).toBe("wss://pivot.example/api/ws/matches/m1");
  });

  it("leaves other hosts alone", () => {
    const url = "wss://hub.webpubsub.azure.com/client/hubs/pivot?access_token=x";
    expect(sameOriginIfLoopback(url, page)).toBe(url);
  });
});
