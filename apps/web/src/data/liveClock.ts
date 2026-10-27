// The simulated live match (C14, #354): one stored match replayed on a clock tied to the wall clock,
// so every visit lands in the middle of it and every viewer sees the same minute. The same anchor
// and break as the API's hub (apps/api/src/pivot_api/hub.py): after the final whistle and a short
// break the match kicks off again.
export const LIVE_ANCHOR = Date.UTC(2026, 9, 27) / 1000;
export const LIVE_BREAK_S = 120;

/** The live match's elapsed second at `nowMs`; past `length` is the break before the next kick-off. */
export function liveClock(length: number, nowMs = Date.now()): number {
  const cycle = Math.max(1, length + LIVE_BREAK_S);
  return Math.floor((((nowMs / 1000 - LIVE_ANCHOR) % cycle) + cycle) % cycle);
}

/** During the break after full time, the milliseconds to the next kick-off; null while the match is on. */
export function msToKickoff(length: number, nowMs = Date.now()): number | null {
  const clock = liveClock(length, nowMs);
  return clock >= length ? (length + LIVE_BREAK_S - clock) * 1000 : null;
}

/** `?live=1`: the match in the link is played as the simulated live match. */
export const isLiveLink = (search: string) => new URLSearchParams(search).get("live") === "1";

/** Back to the match page from one of its own pages: the same link when it names the match, else the match alone. */
export const boardHref = (matchId: string, search: string) =>
  new URLSearchParams(search).has("match") ? `/${search}` : `/?match=${encodeURIComponent(matchId)}`;

/** The link to the live match, opened on its replay ("Live") tab. */
export const liveHref = (matchId: string) => `/?match=${encodeURIComponent(matchId)}&live=1&tab=replay`;
