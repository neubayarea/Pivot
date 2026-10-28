// The analyst's post-match report (C19, #385): GET /api/matches/{id}/analysis, worked out on the API
// with the verifier's StatCalculator (phases and game states over time windows, xPts by simulating the
// shots with a fixed seed). The page draws it and works nothing out itself.
//
// Until that endpoint answers, the sections that need it are not drawn at all: no made-up number
// ever shows on the page. A typed sample of the shape lives with the tests (analysis.sample.ts).
import { useVizData } from "./viz";

export type Side = "home" | "away";

// A live match sends null for anything not reached yet (a block still to come, a share with no ball
// yet): every number below can be null, and the page shows "–" or leaves the part out.
type N = number | null;
export type PhaseLine = { xg: N; field_tilt_pct: N; possession_pct: N; ppda: N; shots: N };
export type Phase = { from: number; to: number; home: PhaseLine; away: PhaseLine };

export type StateLine = { xg_per90: N; xga_per90: N; possession_pct: N; field_tilt_pct: N };
/** A score state, seen from the home side's scoreline: level, home ahead, away ahead. */
export type GameState = { state: "level" | "home_leading" | "away_leading"; minutes: N; home: StateLine; away: StateLine };

export type ShotSource = "open_play" | "set_piece" | "penalty" | "counter";
export type ShotQualityLine = { shots: N; xg_per_shot: N; big_chances: N; by_source: Record<ShotSource, N> };

export type LaneLine = { entries: N; xg: N };
export type Lanes = Record<"left" | "centre" | "right", LaneLine>;

export type MatchAnalysis = {
  deserved: { n_sims: number; home_win: N; draw: N; away_win: N; xpts: Record<Side, N> };
  phases: Phase[];
  game_state: GameState[];
  shot_quality: Record<Side, ShotQualityLine>;
  lanes: Record<Side, Lanes>;
  profile: { baseline_matches: number; metrics: string[]; home: N[]; away: N[] };
};

/** A real number, not null or NaN. */
export const isNum = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);

/** A phase the match has reached: at least one of its numbers is there. */
export const reached = (p: Phase) => (["home", "away"] as const).some((s) => Object.values(p[s]).some(isNum));

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
