import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Envelope } from "@pivot/contracts";
import { LiveSocket, type ConnectionStatus, type LiveSocketOptions, type SocketLike } from "./socket";

class FakeSocket implements SocketLike {
  onopen: SocketLike["onopen"] = null;
  onmessage: SocketLike["onmessage"] = null;
  onclose: SocketLike["onclose"] = null;
  onerror: SocketLike["onerror"] = null;
  closed = false;
  constructor(readonly url: string) {}
  open() {
    this.onopen?.({});
  }
  send(...seqs: number[]) {
    for (const seq of seqs) this.onmessage?.({ data: JSON.stringify(env(seq)) });
  }
  /** The server going away. */
  drop(code = 1006) {
    this.closed = true;
    this.onclose?.({ code, reason: "" });
  }
  close() {
    if (!this.closed) this.drop(1000);
  }
}

const env = (seq: number): Envelope => ({ type: "metric.updated", match_id: "m1", seq, ts: "", payload: { seq } });

function setup(over: Partial<LiveSocketOptions> = {}) {
  const sockets: FakeSocket[] = [];
  const seen: number[] = [];
  const statuses: ConnectionStatus[] = [];
  const resyncs: boolean[] = [];
  let release: () => void = () => {};
  let reject: () => void = () => {};
  const opts: LiveSocketOptions = {
    negotiate: async () => "ws://api/ws/matches/m1",
    resync: (full) => {
      resyncs.push(full);
      return new Promise<void>((res, rej) => {
        release = res;
        reject = () => rej(new Error("rest down"));
      });
    },
    onEnvelope: (e) => seen.push(e.seq),
    onStatus: (s) => statuses.push(s),
    createSocket: (url) => {
      const s = new FakeSocket(url);
      sockets.push(s);
      return s;
    },
    random: () => 0,
    ...over,
  };
  const client = new LiveSocket(opts);
  const last = () => sockets[sockets.length - 1];
  /** Let the pending negotiate / resync promises settle. */
  const flush = () => vi.advanceTimersByTimeAsync(0);
  /** Start, open, and finish the first REST load. */
  const connect = async () => {
    client.start();
    await flush();
    last().open();
    release();
    await flush();
  };
  return { client, sockets, seen, statuses, resyncs, last, flush, connect, release: () => release(), reject: () => reject() };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("LiveSocket", () => {
  it("loads REST after connecting and applies frames that arrived meanwhile in seq order", async () => {
    const t = setup();
    t.client.start();
    await t.flush();
    t.last().open();
    expect(t.resyncs).toEqual([true]);
    t.last().send(6, 5);
    expect(t.seen).toEqual([]);
    t.release();
    await t.flush();
    expect(t.seen).toEqual([5, 6]);
    t.last().send(7);
    expect(t.seen).toEqual([5, 6, 7]);
    expect(t.client.current.state).toBe("live");
  });

  it("drops duplicate frames", async () => {
    const t = setup();
    await t.connect();
    t.last().send(1, 2, 2, 1, 3);
    expect(t.seen).toEqual([1, 2, 3]);
  });

  it("reconnects with exponential backoff and since=<last seq>", async () => {
    const t = setup({ baseDelayMs: 100, maxDelayMs: 1000 });
    await t.connect();
    t.last().send(1, 2, 3);

    t.last().drop();
    expect(t.statuses.at(-1)).toEqual({ state: "reconnecting", attempt: 1 });
    await vi.advanceTimersByTimeAsync(99);
    expect(t.sockets).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(t.sockets).toHaveLength(2);
    expect(t.last().url).toBe("ws://api/ws/matches/m1?since=3");

    // Still down: the wait doubles each time, up to the cap.
    t.last().drop();
    expect(t.statuses.at(-1)).toEqual({ state: "reconnecting", attempt: 2 });
    await vi.advanceTimersByTimeAsync(199);
    expect(t.sockets).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(t.sockets).toHaveLength(3);
    for (const wait of [400, 800, 1000, 1000]) {
      t.last().drop();
      await vi.advanceTimersByTimeAsync(wait);
    }
    expect(t.sockets).toHaveLength(7);

    t.last().open();
    expect(t.statuses.at(-1)).toEqual({ state: "live", attempt: 0 });
    // The server resends what was missed (seq > since), then live frames, while REST reloads
    // once; a live frame that repeats a resent one is applied only once.
    t.last().send(4, 5, 5);
    expect(t.resyncs).toEqual([true, false]);
    t.release();
    await t.flush();
    t.last().send(6, 6);
    expect(t.seen).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it("keeps retrying when negotiate fails, and Retry now skips the wait", async () => {
    let up = false;
    const t = setup({
      baseDelayMs: 1000,
      negotiate: async () => {
        if (!up) throw new Error("api down");
        return "ws://api/ws/matches/m1";
      },
    });
    t.client.start();
    await t.flush();
    expect(t.statuses.at(-1)).toEqual({ state: "reconnecting", attempt: 1 });
    await vi.advanceTimersByTimeAsync(1000);
    expect(t.statuses.at(-1)).toEqual({ state: "reconnecting", attempt: 2 });

    up = true;
    t.client.retryNow();
    await t.flush();
    expect(t.sockets).toHaveLength(1);
    t.last().open();
    expect(t.client.current.state).toBe("live");
    // The pending backoff timer was cancelled, so no second socket shows up.
    await vi.advanceTimersByTimeAsync(10_000);
    expect(t.sockets).toHaveLength(1);
  });

  it("reloads over REST when a seq is skipped, then carries on from the held frames", async () => {
    const t = setup();
    await t.connect();
    t.last().send(1, 2);
    t.last().send(5, 6); // 3 and 4 never arrived
    expect(t.seen).toEqual([1, 2]);
    expect(t.resyncs).toEqual([true, false]);
    t.last().send(7);
    t.release();
    await t.flush();
    expect(t.seen).toEqual([1, 2, 5, 6, 7]);
    t.last().send(8);
    expect(t.seen.at(-1)).toBe(8);
  });

  it("reloads over REST when the resend after a reconnect starts past since+1", async () => {
    const t = setup({ baseDelayMs: 10 });
    await t.connect();
    t.last().send(1, 2);
    t.last().drop();
    await vi.advanceTimersByTimeAsync(10);
    t.last().open();
    t.last().send(40, 41); // the server's resend buffer no longer holds 3..39
    expect(t.resyncs).toEqual([true, false]);
    t.release();
    await t.flush();
    expect(t.seen).toEqual([1, 2, 40, 41]);
  });

  it("rebases on a full reload when the server restarted and seq began again", async () => {
    const t = setup({ baseDelayMs: 10 });
    await t.connect();
    t.last().send(1, 2, 3, 4, 5);
    t.last().drop();
    await vi.advanceTimersByTimeAsync(10);
    t.last().open();
    t.last().send(1, 2);
    // The reconnect reload was already running; a full one follows it.
    expect(t.resyncs).toEqual([true, false]);
    t.release();
    await t.flush();
    expect(t.resyncs).toEqual([true, false, true]);
    expect(t.seen).toEqual([1, 2, 3, 4, 5]);
    t.release();
    await t.flush();
    t.last().send(3);
    expect(t.seen).toEqual([1, 2, 3, 4, 5, 1, 2, 3]);
    expect(t.client.seq).toBe(3);
  });

  it("rebases when the first frame after a restart arrives after the reconnect reload", async () => {
    const t = setup({ baseDelayMs: 10 });
    await t.connect();
    t.last().send(1, 2, 3);
    t.last().drop();
    await vi.advanceTimersByTimeAsync(10);
    t.last().open();
    t.release();
    await t.flush();
    t.last().send(1);
    expect(t.resyncs).toEqual([true, false, true]);
    t.release();
    await t.flush();
    expect(t.seen).toEqual([1, 2, 3, 1]);
  });

  it("closes and retries when the REST reload fails, keeping the held frames", async () => {
    const t = setup({ baseDelayMs: 10 });
    t.client.start();
    await t.flush();
    t.last().open();
    t.last().send(1, 2);
    t.reject();
    await t.flush();
    expect(t.last().closed).toBe(true);
    expect(t.client.current.state).toBe("reconnecting");

    await vi.advanceTimersByTimeAsync(10);
    expect(t.last().url).toBe("ws://api/ws/matches/m1"); // nothing applied yet, so no since
    t.last().open();
    expect(t.resyncs).toEqual([true, true]);
    t.last().send(2, 3);
    t.release();
    await t.flush();
    expect(t.seen).toEqual([1, 2, 3]);
  });

  it("stops for good on 4404 and after stop()", async () => {
    const t = setup({ baseDelayMs: 10 });
    await t.connect();
    t.last().drop(4404);
    expect(t.client.current).toMatchObject({ state: "failed", reason: "Match not found" });
    await vi.advanceTimersByTimeAsync(1000);
    expect(t.sockets).toHaveLength(1);

    const u = setup({ baseDelayMs: 10 });
    await u.connect();
    u.client.stop();
    expect(u.last().closed).toBe(true);
    await vi.advanceTimersByTimeAsync(1000);
    expect(u.sockets).toHaveLength(1);
  });
});
