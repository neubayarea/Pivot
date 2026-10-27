// The deeper pre-match data (#315): `GET /api/matches/{id}/prematch` (#314), worked out by the API
// from the season file before this match's matchday. The types follow the final shape momomojun
// posted on #314 (only the fields the page reads); they move to `@pivot/contracts` when it lands. Every part may be missing (a match the
// season file does not know, a team with no games yet), and the page then leaves it out.
import { useVizData } from "./viz";

export type Pair = [number, number];
export type Wdl = "W" | "D" | "L";
export type Level = "low" | "medium" | "high";
export type Period = "0-15" | "16-30" | "31-45" | "46-60" | "61-75" | "76-90";
export const PERIODS: readonly Period[] = ["0-15", "16-30", "31-45", "46-60", "61-75", "76-90"];

export type TeamRecord = { played: number; w: number; d: number; l: number; gf: number; ga: number; pts: number; ppg: number; position?: number | null };

/** One of the last five, newest first, from the team's side: `ft` and `ht` are [this team, the opponent]. */
export type RecentGame = {
  season?: number; matchday: number; opponent: string; opponent_id?: string; venue: "H" | "A"; ft: Pair; ht: Pair | null; result: Wdl;
  scored_first: boolean | null; came_from_behind: boolean | null;
  /** Led at some point and did not win; worked out from `ht` and `ft` when the API leaves it out. */
  lead_dropped?: boolean | null;
};

export type RecentStats = {
  /** How many games the numbers cover (normally 5). */
  games?: number;
  gf_avg: number | null; ga_avg: number | null; clean_sheets: number | null; failed_to_score: number | null;
  btts: number | null; over_2_5: number | null; scored_first: number | null;
  ht_lead_won?: number | null; ht_lead_dropped?: number | null;
  goals_by_period: Partial<Record<Period, number>> | null; conceded_by_period: Partial<Record<Period, number>> | null;
  reds: number | null; avg_rating: number | null;
};

export type NextFixture = {
  competition: string; stage?: string | null; matchday?: number | null; opponent: string; opponent_id?: string;
  venue: "H" | "A"; days_until: number;
  importance: Level; rotation_risk: Level; rotation_note?: string | null;
  rotation_note_key?: string | null; rotation_params?: Record<string, string | number> | null;
  /** A cup or European tie made up for the demo season (#314); league games come from the real fixture list. */
  fictional?: boolean;
};

/** The usual XI (started 3 of the last `games` league games) against today's starters. */
export type UsualXi = { regulars_starting: number; regulars_benched: string[]; newcomers: string[]; games?: number; regulars?: string[] };

export type TeamPreMatch = {
  club_id?: string; name?: string;
  overall: TeamRecord | null; home_only: TeamRecord | null; away_only: TeamRecord | null;
  last5: RecentGame[]; last5_stats: RecentStats | null;
  /** The nearest next game: a cup tie when one comes first, else the same as `next_league`. */
  next_fixture: NextFixture | null; next_league?: NextFixture | null; usual_xi_today: UsualXi | null;
};

export type Tally = { played: number; home_w: number; d: number; away_w: number };
/** A past meeting, oldest first; `ft` and `ht` are [that game's home club, its away club]. */
export type Meeting = {
  season: number; matchday?: number | null; venue_club: string; home_club?: string; away_club?: string; ft: Pair; ht: Pair | null;
};

export type PreMatchReport = {
  match_id: string;
  season?: number;
  matchday: number | null;
  /** One line: pre-match context only, cup ties made up, half-time scores estimated. */
  about?: string | null; about_key?: string | null;
  teams: { home: TeamPreMatch | null; away: TeamPreMatch | null };
  head_to_head: { all: Tally | null; at_this_ground: Tally | null; meetings: Meeting[] } | null;
};

export const usePreMatchReport = (matchId: string | null) =>
  useVizData<PreMatchReport>(matchId ? `/api/matches/${encodeURIComponent(matchId)}/prematch` : null);

/** A record with games in it; an empty one is left out, never shown as zeros. */
export const played = (r: TeamRecord | null | undefined): r is TeamRecord => !!r && r.played > 0;

/** Led at some point and did not win: the API's flag, else a half-time lead that was not kept. */
export const leadDropped = (g: RecentGame) =>
  g.lead_dropped ?? (g.ht ? g.ht[0] > g.ht[1] && g.result !== "W" : null);

/** The labels on one game: a comeback, scoring first, a lead that slipped. */
export type GameTag = "comeback" | "first" | "dropped";
export function gameTags(g: RecentGame): GameTag[] {
  const tags: GameTag[] = [];
  if (g.came_from_behind) tags.push("comeback");
  if (g.scored_first) tags.push("first");
  if (leadDropped(g)) tags.push("dropped");
  return tags;
}
