// Which part of the match page is open (Ax59): before, during or after the match, Premier League
// style. It lives in the link (`?match=…&tab=pre|live|post`) so a recording or a shared link opens
// straight on it; anything else, or nothing, is the live tab.
import { useLocation } from "react-router-dom";

export const TABS = ["pre", "live", "post"] as const;
export type MatchTab = (typeof TABS)[number];
export const DEFAULT_TAB: MatchTab = "live";

export function tabFrom(search: string): MatchTab {
  const asked = new URLSearchParams(search).get("tab");
  return TABS.find((t) => t === asked) ?? DEFAULT_TAB;
}

/** The same link with another tab open; the match, replay and viewer settings in it stay. */
export function tabSearch(search: string, tab: MatchTab): string {
  const q = new URLSearchParams(search);
  q.set("tab", tab);
  return `?${q}`;
}

export const useTab = (): MatchTab => tabFrom(useLocation().search);
