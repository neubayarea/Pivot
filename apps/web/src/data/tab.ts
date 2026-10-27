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

/** The Ax59 tabs, for links recorded before C13. */
const OLD: Record<string, MatchTab> = { pre: "preview", live: "replay", post: "overview" };

/** The tab a match opens on when the link names none. */
export function defaultTab(status: Match["status"] | undefined): MatchTab {
  if (status === "scheduled") return "preview";
  if (status === "live" || status === "paused") return "replay";
  return "overview";
}

export function tabFrom(search: string, status?: Match["status"]): MatchTab {
  const asked = new URLSearchParams(search).get("tab") ?? "";
  return TABS.find((t) => t === asked) ?? OLD[asked] ?? defaultTab(status);
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
  return tabFrom(search, match.status);
}
