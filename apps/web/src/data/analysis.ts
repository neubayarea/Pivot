// The analyst's post-match report (C19, #385): GET /api/matches/{id}/analysis, worked out on the API
// with the verifier's StatCalculator (phases and game states over time windows, xPts by simulating the
// shots with a fixed seed). The page draws it and works nothing out itself.
//
// Until that endpoint is live, the report draws a typed SAMPLE of the same shape, and says so on the
// page ("sample data"), so no made-up number passes for the match's own.
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

/** A made-up report of the right shape, for the page to draw until the endpoint is live. */
export const SAMPLE_ANALYSIS: MatchAnalysis = {
  deserved: { n_sims: 10000, home_win: 0.24, draw: 0.27, away_win: 0.49, xpts: { home: 0.99, away: 1.74 } },
  phases: [
    { from: 0, to: 15, home: { xg: 0.18, field_tilt_pct: 54, possession_pct: 53, ppda: 7.2, shots: 2 }, away: { xg: 0.05, field_tilt_pct: 46, possession_pct: 47, ppda: 9.1, shots: 1 } },
    { from: 15, to: 30, home: { xg: 0.12, field_tilt_pct: 41, possession_pct: 46, ppda: 6.4, shots: 2 }, away: { xg: 0.86, field_tilt_pct: 59, possession_pct: 54, ppda: 4.8, shots: 3 } },
    { from: 30, to: 45, home: { xg: 0.45, field_tilt_pct: 48, possession_pct: 50, ppda: 5.9, shots: 3 }, away: { xg: 0.95, field_tilt_pct: 52, possession_pct: 50, ppda: 5.2, shots: 2 } },
    { from: 45, to: 60, home: { xg: 0.37, field_tilt_pct: 63, possession_pct: 55, ppda: 4.1, shots: 2 }, away: { xg: 0.03, field_tilt_pct: 37, possession_pct: 45, ppda: 8.8, shots: 1 } },
    { from: 60, to: 75, home: { xg: 0.29, field_tilt_pct: 60, possession_pct: 52, ppda: 4.6, shots: 3 }, away: { xg: 0.16, field_tilt_pct: 40, possession_pct: 48, ppda: 6.9, shots: 2 } },
    { from: 75, to: 90, home: { xg: 0.22, field_tilt_pct: 32, possession_pct: 47, ppda: 7.8, shots: 2 }, away: { xg: 0.23, field_tilt_pct: 68, possession_pct: 53, ppda: 3.9, shots: 4 } },
  ],
  game_state: [
    { state: "level", minutes: 41, home: { xg_per90: 1.62, xga_per90: 1.21, possession_pct: 51, field_tilt_pct: 52 }, away: { xg_per90: 1.21, xga_per90: 1.62, possession_pct: 49, field_tilt_pct: 48 } },
    { state: "home_leading", minutes: 15, home: { xg_per90: 0.84, xga_per90: 1.38, possession_pct: 44, field_tilt_pct: 35 }, away: { xg_per90: 1.38, xga_per90: 0.84, possession_pct: 56, field_tilt_pct: 65 } },
    { state: "away_leading", minutes: 42, home: { xg_per90: 1.35, xga_per90: 3.06, possession_pct: 52, field_tilt_pct: 58 }, away: { xg_per90: 3.06, xga_per90: 1.35, possession_pct: 48, field_tilt_pct: 42 } },
  ],
  shot_quality: {
    home: { shots: 14, xg_per_shot: 0.12, big_chances: 1, by_source: { open_play: 1.05, set_piece: 0.24, penalty: 0, counter: 0.34 } },
    away: { shots: 13, xg_per_shot: 0.18, big_chances: 3, by_source: { open_play: 1.12, set_piece: 0.38, penalty: 0.76, counter: 0.02 } },
  },
  lanes: {
    home: { left: { entries: 14, xg: 0.41 }, centre: { entries: 9, xg: 0.78 }, right: { entries: 11, xg: 0.44 } },
    away: { left: { entries: 8, xg: 0.35 }, centre: { entries: 12, xg: 1.41 }, right: { entries: 15, xg: 0.52 } },
  },
  profile: {
    baseline_matches: 20,
    metrics: ["xg", "shots", "possession_pct", "field_tilt_pct", "progressive_passes", "ppda", "line_height_m", "tackles_won"],
    home: [48, 62, 55, 71, 80, 66, 35, 30], away: [83, 57, 45, 29, 41, 88, 30, 74],
  },
};

/** The match's analysis, or the sample (with `sample: true`) while the endpoint is not there. */
export function useAnalysis(matchId: string | null, upTo: number | null = null): { data: MatchAnalysis | null; sample: boolean; loading: boolean } {
  const q = upTo === null ? "" : `?up_to=${Math.floor(Math.max(0, upTo) / 60) * 60}`;
  const state = useVizData<MatchAnalysis>(matchId ? `/api/matches/${encodeURIComponent(matchId)}/analysis${q}` : null);
  if (state.data) return { data: state.data, sample: false, loading: false };
  if (state.error) return { data: SAMPLE_ANALYSIS, sample: true, loading: false };
  return { data: null, sample: false, loading: state.loading };
}

/** The 15-minute block a clock label falls in ("45+2'" stays in the block that ends at 45). */
export function blockOf(phases: readonly Phase[], label: string): number {
  const m = /^(\d+)/.exec(label.trim());
  if (!m) return -1;
  const base = Number(m[1]);
  return phases.findIndex((p, i) => (base > p.from && base <= p.to) || (i === phases.length - 1 && base > p.to));
}
