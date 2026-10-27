// Who is watching, and what that changes on the page (C12, #311). Fan or analyst, the ♥ team and
// the ★ player each change *what* a page shows and in what order, not only the words. Every page
// reads `usePersona()`; the helpers below are pure so the pre-match, live and post-match tabs
// pick the same "your team's strongest stats" and the same best player.
import type { PlayerReport, PlayerStatsReport, Pivot1 as Pivot, Score, TeamStatsReport, TeamStatsScope } from "@pivot/contracts";
import { usePrefs } from "../i18n";
import type { Side } from "./view";
import { useVizData } from "./viz";

export type Audience = "fan" | "analyst";
/** Fans get five plain team stats; analysts the full grouped table (#279). */
export type StatsLevel = "fan5" | "all23";
/** A turning point that swung to the viewer's team, away from it, or no team picked. */
export type Lean = "for" | "against" | null;
export type Result = "win" | "draw" | "loss";
/** Goals each side, as in the score. */
export type Goals = Pick<Score, "home" | "away">;

/** The five team stats a fan sees: no indices, no xG numbers. */
export const FAN5 = ["possession_pct", "shots", "shots_on_target", "box_entries", "distance_covered_km"] as const;
/** The fan's team-stats card (C13 UX): six plain numbers in one table, attack and defence both. */
export const FAN_STATS = ["possession_pct", "shots", "shots_on_target", "box_entries", "tackles_won", "distance_covered_km"] as const;

/**
 * Which way is better for the team, for the stats where "more" has one meaning. PPDA and turnovers
 * read the other way round (fewer passes allowed is the harder press). Shape (line height, width,
 * press distance) and average momentum have no better side, so they are never a strength or weakness.
 */
export const BETTER: Record<string, 1 | -1> = {
  shots: 1, shots_on_target: 1, xg: 1, xa: 1, box_entries: 1, threat_total: 1,
  possession_pct: 1, passes: 1, pass_accuracy_pct: 1, passes_final_third: 1, progressive_passes: 1, field_tilt_pct: 1,
  tackles_won: 1, interceptions: 1, duels_won: 1, pressures: 1, distance_covered_km: 1,
  turnovers: -1, ppda: -1,
};

/** Section ids per tab, in the order each audience reads them. Pages render the ones they have. */
export const ORDER = {
  fan: {
    pre: ["yourTeam", "spotlight", "stories", "form", "headToHead", "plan", "lineups"],
    live: ["spotlight", "yourTeam", "pitch", "stats", "pictures", "events"],
    post: ["yourTeam", "spotlight", "story", "momentum", "keys", "setPieces", "trace"],
  },
  analyst: {
    pre: ["form", "headToHead", "plan", "lineups", "yourTeam", "spotlight", "stories"],
    live: ["pitch", "stats", "events", "teamStats", "pictures", "spotlight", "yourTeam"],
    post: ["yourTeam", "momentum", "pivots", "teamStats", "keys", "setPieces", "spotlight", "trace"],
  },
} as const satisfies Record<Audience, Record<"pre" | "live" | "post", readonly string[]>>;

export const other = (s: Side): Side => (s === "home" ? "away" : "home");

/** "for" when the pivot swung to the picked team, "against" when away from it, null with no team picked. */
export const lean = (p: Pick<Pivot, "direction">, side: Side | null): Lean =>
  side === null ? null : p.direction === side ? "for" : "against";

export const result = (score: Goals, side: Side): Result => {
  const d = score[side] - score[other(side)];
  return d > 0 ? "win" : d < 0 ? "loss" : "draw";
};

export type StatEdge = { metric: string; mine: number; theirs: number; /** Relative gap, > 0 in the team's favour. */ gap: number };

/** Every stat with a better side, as the team's relative edge over the other: (mine − theirs) / mean, signed by BETTER. */
export function statEdges(report: TeamStatsReport | null | undefined, side: Side, scope: TeamStatsScope["scope"] = "match"): StatEdge[] {
  const s = report?.scopes.find((x) => x.scope === scope);
  if (!s) return [];
  const out: StatEdge[] = [];
  for (const m of report!.metrics) {
    const dir = BETTER[m.metric];
    const mine = s[side][m.metric];
    const theirs = s[other(side)][m.metric];
    if (!dir || mine === null || mine === undefined || theirs === null || theirs === undefined) continue;
    const mean = (Math.abs(mine) + Math.abs(theirs)) / 2;
    if (mean === 0) continue;
    out.push({ metric: m.metric, mine, theirs, gap: (dir * (mine - theirs)) / mean });
  }
  return out;
}

/** The team's `n` biggest edges (strengths) and `n` biggest deficits (weaknesses); a level stat is neither. */
export function strengthsAndWeaknesses(report: TeamStatsReport | null | undefined, side: Side, n = 3, only?: ReadonlySet<string>) {
  const edges = statEdges(report, side).filter((e) => !only || only.has(e.metric));
  const strengths = edges.filter((e) => e.gap > 0.02).sort((a, b) => b.gap - a.gap).slice(0, n);
  const weaknesses = edges.filter((e) => e.gap < -0.02).sort((a, b) => a.gap - b.gap).slice(0, n);
  return { strengths, weaknesses };
}

/** The best-rated player who played at least 20 minutes, of one team or of the match. */
export function bestPlayer(players: readonly PlayerReport[], side?: Side): PlayerReport | null {
  const pool = players.filter((p) => p.stats && p.stats.minutes_played >= 20 && (!side || p.team === side));
  return pool.reduce<PlayerReport | null>((best, p) => (!best || p.stats!.rating > best.stats!.rating ? p : best), null);
}

/** The team's average rating over players who played at least 20 minutes; null with none. */
export function teamRating(players: readonly PlayerReport[], side: Side): number | null {
  const r = players.filter((p) => p.team === side && p.stats && p.stats.minutes_played >= 20).map((p) => p.stats!.rating);
  return r.length ? r.reduce((a, b) => a + b, 0) / r.length : null;
}

export type StatKey = keyof NonNullable<PlayerReport["stats"]>;

/** The line a position code belongs to, for words a fan reads: "AM" is a midfielder (C13 QA). */
export function roleGroup(role: string): "gk" | "def" | "mid" | "fwd" {
  const r = role.toUpperCase();
  if (r === "GK") return "gk";
  if (/^(CB|LB|RB|LWB|RWB|SW)$/.test(r)) return "def";
  if (/^(DM|CDM|CM|LM|RM|AM|CAM)$/.test(r)) return "mid";
  return "fwd";
}

/** The six numbers that say most about a player in his position. */
export function coreStats(role: string): StatKey[] {
  const r = role.toUpperCase();
  if (r === "GK") return ["saves", "passes", "pass_accuracy_pct", "progressive_passes", "distance_km", "top_speed_kmh"];
  if (/^(CB|LB|RB|LWB|RWB|SW)$/.test(r)) return ["tackles_won", "interceptions", "aerials_won", "duels_won", "progressive_passes", "pass_accuracy_pct"];
  if (/^(DM|CDM|CM|LM|RM|AM|CAM)$/.test(r)) return ["passes", "pass_accuracy_pct", "key_passes", "progressive_passes", "tackles_won", "distance_km"];
  return ["goals", "shots", "xg", "key_passes", "dribbles_won", "sprints"];
}

/** What the viewer's settings change, for every page. */
export function usePersona() {
  const { prefs } = usePrefs();
  const audience: Audience = prefs.audience === "fan" ? "fan" : "analyst";
  const side: Side | null = prefs.focus_team ?? null;
  const player = prefs.focus_player_id ?? null;
  return {
    audience,
    fan: audience === "fan",
    statsLevel: (audience === "fan" ? "fan5" : "all23") as StatsLevel,
    side,
    player,
    lean: (p: Pick<Pivot, "direction">) => lean(p, side),
    isForYou: (p: Pick<Pivot, "direction">) => side !== null && p.direction === side,
    order: ORDER[audience],
  };
}
export type Persona = ReturnType<typeof usePersona>;

/** "A, B and C" in the page's language; labels start lower case inside an English or Spanish sentence. */
export function listOf(labels: readonly string[], lang: string): string {
  const words = lang === "zh" ? labels : labels.map((l) => l.charAt(0).toLowerCase() + l.slice(1));
  try {
    return new Intl.ListFormat(lang === "zh" ? "zh-CN" : lang, { style: "long", type: "conjunction" }).format(words);
  } catch {
    return words.join(", ");
  }
}

type Tr = (key: string, vars?: Record<string, string | number>) => string;

/**
 * The one-sentence template summary of a team's match (no AI): result, where it was ahead and
 * behind, and its best player. "Harbour City drew 3–3. Ahead on shots, box entries and pressures.
 * Behind on duels won. Best player: A. Moreau, rated 7.8."
 */
export function teamLine(t: Tr, lang: string, o: {
  team: string; score: Goals; side: Side; strengths: readonly string[]; weaknesses: readonly string[];
  best?: { name: string; rating: number } | null;
}): string {
  const score = `${o.score[o.side]}–${o.score[other(o.side)]}`;
  const parts = [t(`you.${result(o.score, o.side)}`, { team: o.team, score })];
  if (o.strengths.length) parts.push(t("you.ahead", { list: listOf(o.strengths, lang) }));
  if (o.weaknesses.length) parts.push(t("you.behind", { list: listOf(o.weaknesses, lang) }));
  if (!o.strengths.length && !o.weaknesses.length) parts.push(t("you.level"));
  if (o.best) parts.push(t("you.bestLine", { name: o.best.name, rating: o.best.rating.toFixed(1) }));
  return parts.join(lang === "zh" ? "" : " ");
}

/** Every player's numbers (#226) up to the replay's or live match's minute; null `matchId` fetches nothing. */
export function usePlayers(matchId: string | null, upTo: number | null = null) {
  const q = upTo === null ? "" : `?up_to=${Math.floor(Math.max(0, upTo) / 60) * 60}`;
  return useVizData<PlayerStatsReport>(matchId ? `/api/matches/${encodeURIComponent(matchId)}/players/stats${q}` : null);
}

/**
 * What-if choices in the order that matters to the ♥ team (C12): first what would have helped it
 * (its own red card taken away, the other side's goal ruled out), then its own decisions (its
 * substitutions, its press), then the rest. Same order as given without a team, or among equals.
 */
export function forYourTeam<O extends { type: string; team?: Side | null }>(options: readonly O[], side: Side | null): O[] {
  if (!side) return [...options];
  const score = (o: O) => {
    if (!o.team) return 0;
    if (o.type === "remove_red_card") return o.team === side ? 3 : -1;
    if (o.type === "remove_goal") return o.team === side ? -1 : 3;
    return o.team === side ? 2 : 0;
  };
  return options.map((o, i) => [o, i] as const).sort((a, b) => score(b[0]) - score(a[0]) || a[1] - b[1]).map(([o]) => o);
}

/** The alarm's view of a turning point, from momentum per minute (home +): the mean five minutes before and after, and the swing towards the side it turned to. */
export function swingAt(metrics: readonly { minute: number; momentum: number }[], minute: number, direction: Side, span = 5) {
  const mean = (from: number, to: number) => {
    const v = metrics.filter((m) => m.minute >= from && m.minute < to).map((m) => m.momentum);
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
  };
  const before = mean(minute - span, minute);
  const after = mean(minute, minute + span);
  const swing = before === null || after === null ? null : (after - before) * (direction === "home" ? 1 : -1);
  return { before, after, swing };
}
