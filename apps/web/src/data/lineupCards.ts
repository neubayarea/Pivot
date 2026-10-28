// The line-ups tab's numbers (C21, #401): the three stats a player's card shows for his role, the
// squad's ratings in bands, and what each substitution changed. Every number is the API's
// (/players/stats, /analysis subs, the verifier's StatCalculator); here they are only picked and sorted.
import type { AnalysisSub, PlayerMatchStats, PlayerReport } from "@pivot/contracts";

export type Side = "home" | "away";
export type RoleGroup = "gk" | "def" | "mid" | "fwd";
export type CardStat = "saves" | "passes" | "pass_accuracy_pct" | "tackles_won" | "interceptions" | "progressive_passes"
  | "key_passes" | "xg" | "shots";

const GROUP: Record<string, RoleGroup> = {
  GK: "gk", CB: "def", LB: "def", RB: "def", LWB: "def", RWB: "def",
  DM: "mid", CM: "mid", AM: "mid", LM: "mid", RM: "mid", LW: "fwd", RW: "fwd", ST: "fwd",
};

/** What a keeper, a defender, a midfielder and a forward are judged on first. */
export const CARD_STATS: Record<RoleGroup, readonly CardStat[]> = {
  gk: ["saves", "pass_accuracy_pct", "passes"],
  def: ["tackles_won", "interceptions", "progressive_passes"],
  mid: ["key_passes", "progressive_passes", "pass_accuracy_pct"],
  fwd: ["xg", "shots", "key_passes"],
};

export const roleGroup = (role: string): RoleGroup => GROUP[role] ?? "mid";

/** The card's three stats for the player's role; null where the API has no value. */
export function cardStats(p: Pick<PlayerReport, "role"> & { stats: PlayerMatchStats | null }): { key: CardStat; value: number | null }[] {
  return CARD_STATS[roleGroup(p.role)].map((key) => ({ key, value: p.stats ? (p.stats[key] as number | null) : null }));
}

/** "0.43" for xG, "87%" for a share, "4" for a count. */
export function cardValue(key: CardStat, v: number | null): string {
  if (v === null || !Number.isFinite(v)) return "–";
  if (key === "xg") return v.toFixed(2);
  if (key === "pass_accuracy_pct") return `${Math.round(v)}%`;
  return String(Math.round(v));
}

/** Rating bands, low to high: [from, to) and its label. */
export const BANDS: readonly { from: number; to: number; label: string }[] = [
  { from: 0, to: 6, label: "<6.0" }, { from: 6, to: 6.5, label: "6.0–6.4" }, { from: 6.5, to: 7, label: "6.5–6.9" },
  { from: 7, to: 7.5, label: "7.0–7.4" }, { from: 7.5, to: 8, label: "7.5–7.9" }, { from: 8, to: 11, label: "8.0+" },
];
export const MIN_MINUTES = 20;                  // as the team rating and the player of the match count

/** How many of each side's players (at least MIN_MINUTES played) fall in each band. */
export function ratingSpread(players: readonly PlayerReport[]): Record<Side, number[]> {
  const out: Record<Side, number[]> = { home: BANDS.map(() => 0), away: BANDS.map(() => 0) };
  for (const p of players) {
    if (!p.stats || p.stats.minutes_played < MIN_MINUTES) continue;
    const i = BANDS.findIndex((b) => p.stats!.rating >= b.from && p.stats!.rating < b.to);
    if (i >= 0) out[p.team][i] += 1;
  }
  return out;
}

/** One substitution as the impact table reads it, from the side that made it. */
export type SubImpact = {
  sub: AnalysisSub;
  xg: [number | null, number | null];          // the side's own xG before, after
  xga: [number | null, number | null];         // the opponent's
  tilt: [number | null, number | null];        // the side's field tilt before, after
  tiltChange: number | null;                   // after minus before, in points
};

export function subImpact(sub: AnalysisSub): SubImpact {
  const me = sub.team as Side;
  const them: Side = me === "home" ? "away" : "home";
  const tilt: [number | null, number | null] = [sub.before[me]?.field_tilt_pct ?? null, sub.after[me]?.field_tilt_pct ?? null];
  return {
    sub,
    xg: [sub.before[me]?.xg ?? null, sub.after[me]?.xg ?? null],
    xga: [sub.before[them]?.xg ?? null, sub.after[them]?.xg ?? null],
    tilt,
    tiltChange: tilt[0] !== null && tilt[1] !== null ? Math.round((tilt[1] - tilt[0]) * 10) / 10 : null,
  };
}
