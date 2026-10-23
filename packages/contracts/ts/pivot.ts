/* Generated from packages/contracts/schema/pivot.schema.json by pnpm gen:types. Do not edit by hand. */

/**
 * Generated from packages/pivot_core/src/pivot_core/domain. Do not edit by hand.
 */
export interface Pivot {
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AgentTrace".
 */
export interface AgentTrace {
  agent: "judge" | "explainer" | "verifier" | "template" | "translator" | "executor" | "comparator" | "recap";
  chain_id: string;
  input_ref: string;
  latency_ms: number;
  match_id: string;
  model: string | null;
  output_summary: string;
  prompt_hash: string | null;
  status: "ok" | "rejected" | "retried" | "degraded" | "error";
  step: number;
  tokens: number;
  trace_id: string;
  verdict: Verdict | null;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Verdict".
 */
export interface Verdict {
  issues: VerifierIssue[];
  passed: boolean;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "VerifierIssue".
 */
export interface VerifierIssue {
  code:
    | "sentence_count"
    | "too_long"
    | "evidence_count"
    | "evidence_invalid"
    | "number_mismatch"
    | "direction_mismatch"
    | "significance_unsupported"
    | "banned_term"
    | "schema_invalid";
  message: string;
  sentence_index: number | null;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "BallPosition".
 */
export interface BallPosition {
  owner_id: string | null;
  x: number;
  y: number;
  z: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Claim".
 */
export interface Claim {
  stat_ref: StatRef;
  unit: "count" | "pct" | "xg" | "index" | "m" | "km";
  value: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "StatRef".
 */
export interface StatRef {
  metric:
    | "possession_pct"
    | "passes"
    | "pass_accuracy_pct"
    | "passes_final_third"
    | "box_entries"
    | "shots"
    | "shots_on_target"
    | "xg"
    | "threat_total"
    | "pressures"
    | "tackles_won"
    | "interceptions"
    | "duels_won"
    | "turnovers"
    | "momentum_avg"
    | "line_height_m"
    | "team_width_m"
    | "press_distance_m"
    | "distance_covered_km";
  player_id: string | null;
  team: "home" | "away";
  /**
   * @minItems 2
   * @maxItems 2
   */
  window: [number, number];
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Envelope".
 */
export interface Envelope {
  match_id: string;
  payload: {
    [k: string]: unknown;
  };
  seq: number;
  ts: string;
  type:
    | "match.status"
    | "event.batch"
    | "tracking.frame"
    | "metric.updated"
    | "pivot.pending"
    | "pivot.confirmed"
    | "pivot.degraded"
    | "pivot.rejected"
    | "scenario.progress"
    | "scenario.completed"
    | "trace.appended"
    | "recap.ready";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "ExplanationSentence".
 */
export interface ExplanationSentence {
  claims: Claim[];
  /**
   * @minItems 1
   * @maxItems 4
   */
  evidence_ids: [string, ...string[]];
  text: string;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Match".
 */
export interface Match {
  away: Team;
  clock: number;
  home: Team;
  match_id: string;
  period: 1 | 2;
  preset: string | null;
  score: Score;
  seed: number;
  speed: 1 | 5 | 20 | 60;
  status: "scheduled" | "live" | "paused" | "finished";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Team".
 */
export interface Team {
  color: string;
  formation: string;
  name: string;
  players: Player[];
  short_name: string;
  side: "home" | "away";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Player".
 */
export interface Player {
  name: string;
  player_id: string;
  position: "GK" | "DF" | "MF" | "FW";
  shirt_number: number;
  team: "home" | "away";
}
export interface Score {
  away: number;
  home: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "MatchEvent".
 */
export interface MatchEvent {
  ball_speed_kmh: number | null;
  end_location: [number, number] | null;
  event_id: string;
  /**
   * Threat-grid zone of `location`.
   */
  from_zone: [number, number] | null;
  location: [number, number] | null;
  match_id: string;
  meta: {
    [k: string]: string;
  };
  /**
   * Match minute the event belongs to (0-based, so 62:30 is minute 62).
   */
  minute: number;
  outcome: ("success" | "fail") | null;
  period: 1 | 2;
  play_pattern:
    ("open_play" | "counter" | "corner" | "free_kick" | "throw_in" | "goal_kick" | "kick_off" | "penalty") | null;
  player_id: string | null;
  possession_id: number | null;
  receiver_id: string | null;
  schema_version: 1;
  seq: number;
  shot_outcome: ("goal" | "saved" | "off_target" | "blocked" | "post") | null;
  t: number;
  team: "home" | "away";
  threat: number;
  /**
   * Threat-grid zone of `end_location`.
   */
  to_zone: [number, number] | null;
  type:
    | "pass"
    | "carry"
    | "dribble"
    | "shot"
    | "save"
    | "pressure"
    | "duel"
    | "tackle"
    | "interception"
    | "clearance"
    | "block"
    | "ball_recovery"
    | "foul"
    | "card"
    | "offside"
    | "substitution"
    | "tactical_shift"
    | "kickoff"
    | "period_end";
  under_pressure: boolean;
  xg: number | null;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "MinuteMetric".
 */
export interface MinuteMetric {
  match_id: string;
  minute: number;
  momentum: number;
  pressure_away: number;
  pressure_home: number;
  threat_away: number;
  threat_home: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Narrative".
 */
export interface Narrative {
  chain_id: string | null;
  headline: string;
  prefs: ViewerPrefs;
  /**
   * @minItems 1
   * @maxItems 8
   */
  sentences: [ExplanationSentence, ...ExplanationSentence[]];
  source: "llm" | "template";
  verifier_attempts: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "ViewerPrefs".
 */
export interface ViewerPrefs {
  audience: "analyst" | "fan";
  focus_player_id: string | null;
  focus_team: ("home" | "away") | null;
  language: "en" | "zh" | "es";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "OutcomeDist".
 */
export interface OutcomeDist {
  away_win: number;
  ci95: {
    /**
     * @minItems 2
     * @maxItems 2
     */
    [k: string]: [number, number];
  };
  draw: number;
  home_win: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "OverlayFeed".
 */
export interface OverlayFeed {
  items: OverlayItem[];
  language: "en" | "zh" | "es";
  match_id: string;
  up_to_seq: number;
}
/**
 * One graphic that a broadcast renderer can place on top of the live feed.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "OverlayItem".
 */
export interface OverlayItem {
  headline: string;
  hide_at: number;
  kind: "pivot" | "goal" | "card" | "substitution";
  overlay_id: string;
  player_id: string | null;
  ref_id: string;
  severity: (1 | 2 | 3) | null;
  show_at: number;
  subline: string | null;
  team: "home" | "away";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Pivot".
 */
export interface Pivot1 {
  chain_id: string;
  direction: "home" | "away";
  match_id: string;
  minute: number;
  narrative: Narrative | null;
  pivot_id: string;
  severity: 1 | 2 | 3;
  status: "pending" | "confirmed" | "rejected" | "degraded";
  trigger_event_ids: string[];
}
/**
 * CUSUM alarm, queued for the Judge. Message id is "{match_id}:{minute}".
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PivotCandidate".
 */
export interface PivotCandidate {
  cusum_stat: number;
  direction: "home" | "away";
  key_event_ids: string[];
  match_id: string;
  minute: number;
  swing: number;
  /**
   * @minItems 2
   * @maxItems 2
   */
  window: [number, number];
}
/**
 * Force an event at a given minute. Used by the eval seeds and the demo preset.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PlantSpec".
 */
export interface PlantSpec {
  minute: number;
  params: {
    [k: string]: number | string;
  };
  team: "home" | "away";
  type: "red_card" | "substitution" | "goal" | "press_change" | "formation_change";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PlayerPosition".
 */
export interface PlayerPosition {
  player_id: string;
  speed_ms: number;
  x: number;
  y: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Recap".
 */
export interface Recap {
  final_score: Score1;
  match_id: string;
  narrative: Narrative;
  pivot_ids: string[];
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Score".
 */
export interface Score1 {
  away: number;
  home: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Scenario".
 */
export interface Scenario {
  done: number;
  match_id: string;
  result: SimResult | null;
  scenario_id: string;
  spec: ScenarioSpec;
  status: "queued" | "running" | "completed" | "failed";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "SimResult".
 */
export interface SimResult {
  baseline: OutcomeDist;
  counterfactual: OutcomeDist;
  executor: "local_pool" | "aca_jobs";
  narrative: Narrative | null;
  runtime_ms: number;
  scenario_id: string;
  significant: {
    [k: string]: boolean;
  };
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "ScenarioSpec".
 */
export interface ScenarioSpec {
  at_minute: number;
  n_runs: 200 | 500 | 1000;
  params: {
    [k: string]: number | string;
  };
  pivot_id: string;
  seed_base: number;
  target_event_id: string | null;
  type:
    | "cancel_substitution"
    | "move_substitution"
    | "remove_red_card"
    | "remove_goal"
    | "change_press"
    | "change_formation";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "TrackingFrame".
 */
export interface TrackingFrame {
  ball: BallPosition;
  match_id: string;
  period: 1 | 2;
  /**
   * @maxItems 22
   */
  players: PlayerPosition[];
  possession: ("home" | "away") | null;
  t: number;
}
