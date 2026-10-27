// The deeper pre-match data (#315): `GET /api/matches/{id}/prematch` (#314, #327), worked out by the
// API from the season file before this match's matchday. The types are the contract's `Prematch*`;
// the page still treats every part as possibly missing (a match the season file does not know, a
// team with no games yet) and leaves that part out.
import type {
  PrematchFixture, PrematchFormStats, PrematchGame, PrematchMeeting, PrematchRecord, PrematchReport, PrematchTeam, PrematchText, PrematchUsualXi,
} from "@pivot/contracts";
import { useLang } from "../i18n";
import { useVizData } from "./viz";

export type { PrematchFixture, PrematchFormStats, PrematchGame, PrematchMeeting, PrematchRecord, PrematchReport, PrematchTeam, PrematchUsualXi };
export type Period = "0-15" | "16-30" | "31-45" | "46-60" | "61-75" | "76-90";
export const PERIODS: readonly Period[] = ["0-15", "16-30", "31-45", "46-60", "61-75", "76-90"];

export const usePreMatchReport = (matchId: string | null) =>
  useVizData<PrematchReport>(matchId ? `/api/matches/${encodeURIComponent(matchId)}/prematch` : null);

/**
 * The pre-match tab's news headlines and effect notes in the page's language (#355):
 * `GET /api/matches/{id}/prematch/text?lang=`. The result gives the translation of one English
 * sentence, or null (an English page, no API, a sentence the API could not translate).
 */
export function usePreMatchText(matchId: string | null): (text: string) => string | null {
  const lang = useLang();
  const { data } = useVizData<PrematchText>(
    matchId && lang !== "en" ? `/api/matches/${encodeURIComponent(matchId)}/prematch/text?lang=${lang}` : null,
  );
  return (text) => (data && data.lang === lang ? (data.texts[text] ?? null) : null);
}

/** A record with games in it; an empty one is left out, never shown as zeros. */
export const played = (r: PrematchRecord | null | undefined): r is PrematchRecord => !!r && r.played > 0;

/** Led at half-time and did not win (`ft` and `ht` are [this team, the opponent]). */
export const leadDropped = (g: PrematchGame) => !!g.ht && g.ht[0] > g.ht[1] && g.result !== "W";

/** The labels on one game: a comeback (to win, or to draw), scoring first, a lead that slipped. */
export type GameTag = "comeback" | "levelled" | "first" | "dropped";
export function gameTags(g: PrematchGame): GameTag[] {
  const tags: GameTag[] = [];
  if (g.came_from_behind) tags.push(g.result === "W" ? "comeback" : "levelled");
  if (g.scored_first) tags.push("first");
  if (leadDropped(g)) tags.push("dropped");
  return tags;
}
