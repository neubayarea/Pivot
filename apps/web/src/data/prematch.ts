// The deeper pre-match data (#315): `GET /api/matches/{id}/prematch` (#314, #327), worked out by the
// API from the season file before this match's matchday. The types are the contract's `Prematch*`;
// the page still treats every part as possibly missing (a match the season file does not know, a
// team with no games yet) and leaves that part out.
import type {
  HeadToHead, TeamForm, PrematchFixture, PrematchFormStats, PrematchGame, PrematchMeeting, PrematchRecord, PrematchReport, PrematchTeam, PrematchText, PrematchUsualXi,
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

/**
 * Ax83 (#395): the build-up's form and head-to-head from this report, for a match whose own context
 * has none (a season fixture is built without the seed season's context, so `context.form` is empty
 * and `context.head_to_head` null, while `/prematch` has the table and the meetings).
 */
export function formFromReport(report: PrematchReport | null): TeamForm[] {
  if (!report) return [];
  return (["home", "away"] as const).flatMap((side) => {
    const team = report.teams[side];
    if (!team) return [];
    const last = team.last5.slice().reverse(); // the report is newest first; the form strip ends on the latest
    return [{
      side, league_position: team.overall?.position ?? null, points: team.overall && team.overall.played > 0 ? team.overall.pts : null,
      last_results: last.map((g) => g.result),
      goals_for_last5: last.reduce((n, g) => n + g.ft[0], 0), goals_against_last5: last.reduce((n, g) => n + g.ft[1], 0),
    }];
  });
}

/** The head-to-head in the context's shape (wins counted for today's home and away sides), or null without meetings. */
export function h2hFromReport(report: PrematchReport | null, last = 5): HeadToHead | null {
  const h = report?.head_to_head;
  if (!h?.all?.played) return null;
  return {
    played: h.all.played, home_wins: h.all.home_w, draws: h.all.d, away_wins: h.all.away_w,
    last_meetings: (h.meetings ?? []).slice(-last).map((m) => ({
      season: String(m.season), competition_id: null, home_club_id: m.home_club ?? m.venue_club, away_club_id: m.away_club,
      home_goals: m.ft[0], away_goals: m.ft[1],
    })),
  };
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
