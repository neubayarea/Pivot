// The analyst's post-match report (C19, #385): GET /api/matches/{id}/analysis, worked out on the API
// with the verifier's StatCalculator (phases and game states over time windows, xPts by simulating the
// shots with a fixed seed). The page draws it and works nothing out itself.
//
// Until that endpoint answers, the sections that need it are not drawn at all: no made-up number
// ever shows on the page. A typed sample of the shape lives with the tests (analysis.sample.ts).
import { useVizData } from "./viz";

export type Side = "home" | "away";

export type PhaseLine = { xg: number; field_tilt_pct: number; possession_pct: number; ppda: number | null; shots: number };
export type Phase = { from: number; to: number; home: PhaseLine; away: PhaseLine };

export type StateLine = { xg_per90: number; xga_per90: number; possession_pct: number; field_tilt_pct: number };
/** A score state, seen from the home side's scoreline: level, home ahead, away ahead. */
export type GameState = { state: "level" | "home_leading" | "away_leading"; minutes: number; home: StateLine; away: StateLine };

export type ShotSource = "open_play" | "set_piece" | "penalty" | "counter";
export type ShotQualityLine = { shots: number; xg_per_shot: number; big_chances: number; by_source: Record<ShotSource, number> };

export type LaneLine = { entries: number; xg: number };
export type Lanes = Record<"left" | "centre" | "right", LaneLine>;

export type MatchAnalysis = {
  deserved: { n_sims: number; home_win: number; draw: number; away_win: number; xpts: Record<Side, number> };
  phases: Phase[];
  game_state: GameState[];
  shot_quality: Record<Side, ShotQualityLine>;
  lanes: Record<Side, Lanes>;
  profile: { baseline_matches: number; metrics: string[]; home: number[]; away: number[] };
};

export const SOURCES: readonly ShotSource[] = ["open_play", "set_piece", "counter", "penalty"];

/** The match's analysis, or null while it loads or when the endpoint is not there. */
export function useAnalysis(matchId: string | null, upTo: number | null = null): { data: MatchAnalysis | null; loading: boolean } {
  const q = upTo === null ? "" : `?up_to=${Math.floor(Math.max(0, upTo) / 60) * 60}`;
  const state = useVizData<MatchAnalysis>(matchId ? `/api/matches/${encodeURIComponent(matchId)}/analysis${q}` : null);
  return { data: state.data, loading: state.loading };
}

/** The 15-minute block a clock label falls in ("45+2'" stays in the block that ends at 45). */
export function blockOf(phases: readonly Phase[], label: string): number {
  const m = /^(\d+)/.exec(label.trim());
  if (!m) return -1;
  const base = Number(m[1]);
  return phases.findIndex((p, i) => (base > p.from && base <= p.to) || (i === phases.length - 1 && base > p.to));
}
