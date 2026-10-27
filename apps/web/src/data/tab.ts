// Which part of the match page is open (C13, #316): tabs by content, the way FotMob, Sofascore and
// the Premier League site split a match page, not by time. It lives in the link
// (`?match=…&tab=overview`) so a recording or a shared link opens straight on it. With no tab in
// the link the page opens where the match is: the preview before kick-off, the replay (called Live)
// while it is played, the overview once it is over. Old links (`?tab=pre|live|post`, Ax59) still work.
import { useLocation } from "react-router-dom";
import type { Match } from "@pivot/contracts";
import { useMatch } from "./match";

export const TABS = ["overview", "whatif", "replay", "stats", "lineups", "preview"] as const;
export type MatchTab = (typeof TABS)[number];

/** C14: a fixture of the next round (`S2026-31-LUN-HBC`, apps/api nextround.py) is never played on the
 * site, so it has only these; the others are greyed out. Other scheduled matches can still kick off. */
export const BEFORE_KICKOFF: readonly MatchTab[] = ["lineups", "preview"];
const NEXT_ROUND_ID = /^S\d{4}-\d{2}-[A-Z]+-[A-Z]+$/;

export const notPlayed = (status: Match["status"] | undefined, matchId = "") =>
  status === "scheduled" && NEXT_ROUND_ID.test(matchId);

export const tabOpen = (tab: MatchTab, status: Match["status"] | undefined, matchId = "") =>
  !notPlayed(status, matchId) || BEFORE_KICKOFF.includes(tab);

/** The Ax59 tabs, for links recorded before C13. */
const OLD: Record<string, MatchTab> = { pre: "preview", live: "replay", post: "overview" };

/** The tab a match opens on when the link names none. */
export function defaultTab(status: Match["status"] | undefined): MatchTab {
  if (status === "scheduled") return "preview";
  if (status === "live" || status === "paused") return "replay";
  return "overview";
}

export function tabFrom(search: string, status?: Match["status"], matchId = ""): MatchTab {
  const asked = new URLSearchParams(search).get("tab") ?? "";
  const tab = TABS.find((t) => t === asked) ?? OLD[asked] ?? defaultTab(status);
  return tabOpen(tab, status, matchId) ? tab : defaultTab(status);
}

/** The same link with another tab open; the match, replay and viewer settings in it stay. */
export function tabSearch(search: string, tab: MatchTab): string {
  const q = new URLSearchParams(search);
  q.set("tab", tab);
  return `?${q}`;
}

export function useTab(): MatchTab {
  const { search } = useLocation();
  const { match } = useMatch();
  return tabFrom(search, match.status, match.match_id);
}
