// One match's realtime feed (PR #85): negotiate → WebSocket of Envelope frames, seq strictly
// increasing per match. The client remembers the highest seq it applied, reconnects with
// exponential backoff and `?since=`, and drops duplicates. After each (re)connect, and whenever
// it sees a gap or the server's seq starting over after a restart, it holds frames back while
// `resync()` reloads state over REST, then applies the held frames in seq order.
import type { Envelope } from "@pivot/contracts";

export type ConnectionState = "connecting" | "live" | "reconnecting" | "failed";
export type ConnectionStatus = { state: ConnectionState; attempt: number; reason?: string };

/** The part of the browser WebSocket the client uses, so tests can pass a fake. */
export interface SocketLike {
  onopen: ((ev: unknown) => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onclose: ((ev: { code: number; reason: string }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  close(code?: number, reason?: string): void;
}

export type LiveSocketOptions = {
  negotiate: () => Promise<string>;
  /**
   * Load state over REST. Runs after every (re)connect and every gap. `full` is set the first
   * time and after a server restart, when what is held cannot be built on.
   */
  resync: (full: boolean) => Promise<void>;
  onEnvelope: (envelope: Envelope) => void;
  onStatus?: (status: ConnectionStatus) => void;
  createSocket?: (url: string) => SocketLike;
  /** Backoff: base * 2^(attempt-1), capped, plus up to 25% jitter. */
  baseDelayMs?: number;
  maxDelayMs?: number;
  random?: () => number;
};

/** Close codes from apps/api/src/pivot_api/realtime.py that retrying will not fix. */
const FATAL: Record<number, string> = { 4404: "Match not found", 4501: "Realtime is not served here" };

export class LiveSocket {
  private socket: SocketLike | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private stopped = false;
  private negotiating = false;
  private attempt = 0;
  private lastSeq = -1;
  /** Set until the first REST load succeeds, and again if a resync fails. */
  private needsResync = true;
  private full = true;
  private syncing = false;
  private again = false;
  private held: Envelope[] = [];
  /** True until the first frame of the current connection is handled. */
  private fresh = false;
  private status: ConnectionStatus = { state: "connecting", attempt: 0 };

  constructor(private readonly opts: LiveSocketOptions) {}

  get seq(): number {
    return this.lastSeq;
  }

  get current(): ConnectionStatus {
    return this.status;
  }

  start(): void {
    this.stopped = false;
    void this.connect();
  }

  stop(): void {
    this.stopped = true;
    this.clearTimer();
    this.drop();
  }

  /** Skip the rest of the backoff wait and reconnect now. */
  retryNow(): void {
    if (this.stopped || this.socket || this.negotiating) return;
    this.clearTimer();
    void this.connect();
  }

  private async connect(): Promise<void> {
    this.timer = null;
    let url: string;
    this.negotiating = true;
    try {
      url = await this.opts.negotiate();
    } catch {
      return this.scheduleReconnect();
    } finally {
      this.negotiating = false;
    }
    if (this.stopped) return;
    if (this.lastSeq >= 0) url += `${url.includes("?") ? "&" : "?"}since=${this.lastSeq}`;

    const create = this.opts.createSocket ?? ((u: string) => new WebSocket(u) as unknown as SocketLike);
    const ws = create(url);
    this.socket = ws;
    ws.onopen = () => {
      if (this.socket !== ws) return;
      this.attempt = 0;
      this.fresh = true;
      this.setStatus({ state: "live", attempt: 0 });
      if (this.needsResync) void this.resync();
    };
    ws.onmessage = (ev) => {
      if (this.socket !== ws) return;
      let envelope: Envelope;
      try {
        envelope = JSON.parse(String(ev.data)) as Envelope;
      } catch {
        return;
      }
      if (typeof envelope?.seq === "number") this.receive(envelope);
    };
    ws.onerror = () => {};
    ws.onclose = (ev) => {
      if (this.socket !== ws) return;
      this.socket = null;
      if (this.stopped) return;
      // Reload once after every reconnect: Web PubSub never resends, and a restarted API may have
      // nothing to resend, so no frame would ever reveal the gap.
      this.needsResync = true;
      const fatal = FATAL[ev.code];
      if (fatal) return this.setStatus({ state: "failed", attempt: this.attempt, reason: ev.reason || fatal });
      this.scheduleReconnect();
    };
  }

  private receive(envelope: Envelope): void {
    const first = this.fresh;
    this.fresh = false;
    if (first && this.lastSeq >= 0 && envelope.seq <= this.lastSeq) {
      // The server only resends seq > since, so an older first frame means it restarted and its
      // seq began again: drop what is held and rebase on a full reload.
      this.lastSeq = -1;
      this.full = true;
      this.held = [envelope];
      void this.resync();
    } else if (this.syncing) {
      this.held.push(envelope);
    } else if (this.lastSeq < 0 || envelope.seq === this.lastSeq + 1) {
      this.apply(envelope);
    } else if (envelope.seq > this.lastSeq) {
      this.held.push(envelope);
      void this.resync();
    } // else a frame already applied
  }

  private apply(envelope: Envelope): void {
    this.lastSeq = envelope.seq;
    this.opts.onEnvelope(envelope);
  }

  private async resync(): Promise<void> {
    if (this.syncing) {
      this.again = true; // a restart showed up mid-reload; run once more when this one ends
      return;
    }
    this.syncing = true;
    do {
      this.again = false;
      const full = this.full;
      try {
        await this.opts.resync(full);
      } catch {
        // Keep the held frames and try again on the next connection.
        this.syncing = false;
        this.needsResync = true;
        this.socket?.close();
        return;
      }
      if (!this.again) this.full = false;
    } while (this.again);
    this.syncing = false;
    this.needsResync = false;
    // Everything up to the snapshot is in; apply what arrived meanwhile, oldest first, once each.
    const held = this.held.sort((a, b) => a.seq - b.seq);
    this.held = [];
    for (const envelope of held) if (envelope.seq > this.lastSeq) this.apply(envelope);
  }

  private scheduleReconnect(): void {
    if (this.stopped) return;
    this.attempt++;
    this.setStatus({ state: "reconnecting", attempt: this.attempt });
    const { baseDelayMs = 500, maxDelayMs = 10_000, random = Math.random } = this.opts;
    const delay = Math.min(maxDelayMs, baseDelayMs * 2 ** (this.attempt - 1));
    this.timer = setTimeout(() => void this.connect(), delay + delay * 0.25 * random());
  }

  private setStatus(status: ConnectionStatus): void {
    this.status = status;
    this.opts.onStatus?.(status);
  }

  private clearTimer(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  private drop(): void {
    const ws = this.socket;
    this.socket = null;
    ws?.close();
  }
}
