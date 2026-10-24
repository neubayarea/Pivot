// Which overlay card belongs on screen at a given match clock, and how the page's clock runs.
// Pure functions, so the timing can be tested without a browser or the API.
import type { OverlayCard } from "@pivot/contracts";

/** Matches pivot_api.overlay.MAX_CLOCK: nothing runs past three hours. */
export const MAX_CLOCK = 3 * 3600;

/** "63:20" or "3800" -> elapsed seconds; null for anything else. Same rules as the API's `?clock=`. */
export function parseClock(value: string | null | undefined): number | null {
  if (value == null) return null;
  const v = value.trim();
  const mmss = /^(\d{1,3}):([0-5]\d)$/.exec(v);
  const t = mmss ? Number(mmss[1]) * 60 + Number(mmss[2]) : /^\d+$/.test(v) ? Number(v) : null;
  return t !== null && t <= MAX_CLOCK ? t : null;
}

/** The card on screen at clock t: show_at <= t < hide_at. The API never lets two overlap. */
export function cardAt(cards: readonly OverlayCard[], t: number): OverlayCard | null {
  return cards.find((c) => c.show_at <= t && t < c.hide_at) ?? null;
}

/**
 * How the page decides the clock:
 * - live: follow the match as it is played (the API's current clock)
 * - fixed: hold one moment, `?clock=mm:ss`
 * - replay: run the timeline locally from `?clock=` (default 0) at `?speed=` match seconds per second
 */
export type ClockMode =
  | { kind: "live" }
  | { kind: "fixed"; at: number }
  | { kind: "replay"; from: number; speed: number };

export function clockMode(params: URLSearchParams): ClockMode {
  const at = parseClock(params.get("clock"));
  const speed = Number(params.get("speed"));
  if (params.has("speed") && Number.isFinite(speed) && speed > 0) return { kind: "replay", from: at ?? 0, speed };
  if (at !== null) return { kind: "fixed", at };
  return { kind: "live" };
}

/** Replay clock after `elapsedMs` of wall time, whole seconds, stopping at MAX_CLOCK. */
export function replayClock(mode: { from: number; speed: number }, elapsedMs: number): number {
  return Math.min(MAX_CLOCK, Math.floor(mode.from + (Math.max(0, elapsedMs) / 1000) * mode.speed));
}

/** "●●○" for severity 2 of 3. */
export function severityDots(severity: 1 | 2 | 3): string {
  return "●".repeat(severity) + "○".repeat(3 - severity);
}
