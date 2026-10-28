/* Generated from packages/contracts/schema/pivot.schema.json by pnpm gen:types. Do not edit by hand. */

/**
 * Generated from packages/pivot_core/src/pivot_core/domain and apps/api/src/pivot_api/prematch.py. Do not edit by hand.
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
    | "context_invalid"
    | "schema_invalid";
  message: string;
  sentence_index: number | null;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AnalysisDeserved".
 */
export interface AnalysisDeserved {
  away_win: number;
  draw: number;
  home_win: number;
  n_sims: number;
  xpts: {
    [k: string]: number;
  };
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AnalysisGameState".
 */
export interface AnalysisGameState {
  away: AnalysisStateTeam;
  home: AnalysisStateTeam;
  minutes: number;
  state: "level" | "home_leading" | "away_leading";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AnalysisStateTeam".
 */
export interface AnalysisStateTeam {
  field_tilt_pct: number | null;
  possession_pct: number | null;
  xg_per90: number | null;
  xga_per90: number | null;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AnalysisLane".
 */
export interface AnalysisLane {
  entries: number;
  final_third_entries: number;
  xg: number;
}
/**
 * `from` / `to`: the spell on the match clock (45 is the second half's kick-off); `window`: the
 * elapsed minutes it covers (from <= minute < to).
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AnalysisPhase".
 */
export interface AnalysisPhase {
  away: AnalysisPhaseTeam;
  from: number;
  home: AnalysisPhaseTeam;
  to: number;
  /**
   * @minItems 2
   * @maxItems 2
   */
  window: [number, number];
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AnalysisPhaseTeam".
 */
export interface AnalysisPhaseTeam {
  field_tilt_pct: number | null;
  possession_pct: number | null;
  ppda: number | null;
  shots: number | null;
  xg: number | null;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AnalysisProfile".
 */
export interface AnalysisProfile {
  away: (number | null)[];
  away_values: (number | null)[];
  baseline_matches: number;
  home: (number | null)[];
  home_values: (number | null)[];
  metrics: string[];
}
/**
 * `from` / `to`: elapsed minutes (from <= minute < to); `period`: the period the window starts in.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AnalysisRolling".
 */
export interface AnalysisRolling {
  away: AnalysisPhaseTeam;
  from: number;
  home: AnalysisPhaseTeam;
  period: number;
  to: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AnalysisShotQuality".
 */
export interface AnalysisShotQuality {
  big_chances: number;
  by_source: {
    [k: string]: number;
  };
  shots: number;
  xg_per_shot: number | null;
}
/**
 * One substitution: `minute` is the elapsed minute, `clock` the match clock's (54 for 54').
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AnalysisSub".
 */
export interface AnalysisSub {
  after: {
    [k: string]: AnalysisSubTeam;
  };
  before: {
    [k: string]: AnalysisSubTeam;
  };
  clock: number;
  cut_after: ("kick_off" | "half_time" | "full_time" | "now" | "sub") | null;
  cut_before: ("kick_off" | "half_time" | "full_time" | "now" | "sub") | null;
  event_id: string;
  minute: number;
  minutes_after: number;
  minutes_before: number;
  period: number;
  player_off_id: string | null;
  player_off_name: string | null;
  player_on_id: string | null;
  player_on_name: string | null;
  reason: string | null;
  t: number;
  team: "home" | "away";
  /**
   * @minItems 2
   * @maxItems 2
   */
  window_after: [number, number];
  /**
   * @minItems 2
   * @maxItems 2
   */
  window_before: [number, number];
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AnalysisSubTeam".
 */
export interface AnalysisSubTeam {
  field_tilt_pct: number | null;
  xg: number | null;
}
/**
 * Why an arm came out as it did: its final scores and each team's numbers after the replay start.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "ArmStats".
 */
export interface ArmStats {
  away: TeamRunStats;
  from_t: number;
  home: TeamRunStats;
  n_runs: number;
  top_scores: ScoreShare[];
}
/**
 * What one team did from the replay start to the end, over all runs of an arm (Bx10).
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "TeamRunStats".
 */
export interface TeamRunStats {
  cards: Spread;
  goals: Spread;
  possession_pct: Spread;
  red_cards: Spread;
  scored_share: number;
  shots: Spread;
  shots_on_target: Spread;
  xg: Spread;
}
/**
 * One number over all runs of an arm: its mean, standard deviation and 10th/90th percentiles.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Spread".
 */
export interface Spread {
  mean: number;
  p10: number;
  p90: number;
  sd: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "ScoreShare".
 */
export interface ScoreShare {
  away: number;
  home: number;
  share: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AttackingAttributes".
 */
export interface AttackingAttributes {
  crossing: number;
  finishing: number;
  heading_accuracy: number;
  short_passing: number;
  volleys: number;
}
/**
 * Six headline ratings, weighted from the detailed ones (an approximation of game cards).
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AttributeSummary".
 */
export interface AttributeSummary {
  defending: number;
  dribbling: number;
  pace: number;
  passing: number;
  physical: number;
  shooting: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AveragePosition".
 */
export interface AveragePosition {
  in_possession: PitchPoint | null;
  out_of_possession: PitchPoint | null;
  player_id: string;
  seconds: number;
  team: "home" | "away";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PitchPoint".
 */
export interface PitchPoint {
  x: number;
  y: number;
}
/**
 * GET /api/matches/{id}/positions: everyone who played, from the tracking frames.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "AveragePositionsReport".
 */
export interface AveragePositionsReport {
  match_id: string;
  period: (1 | 2 | 3 | 4 | 5) | null;
  players: AveragePosition[];
  up_to_t: number;
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
 * via the `definition` "CareerStint".
 */
export interface CareerStint {
  appearances: number;
  as_coach: boolean;
  club_id: string;
  club_name: string;
  departure: ("transfer" | "loan_end" | "released" | "contract_end" | "sacked" | "resigned") | null;
  departure_mood: "amicable" | "neutral" | "acrimonious";
  from_year: number;
  goals: number;
  loan: boolean;
  stint_id: string;
  to_year: number | null;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Claim".
 */
export interface Claim {
  stat_ref: StatRef;
  unit: "count" | "pct" | "xg" | "index" | "m" | "km" | "ratio";
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
    | "distance_covered_km"
    | "progressive_passes"
    | "ppda"
    | "xa"
    | "field_tilt_pct";
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
 * via the `definition` "Coach".
 */
export interface Coach {
  age: number;
  attributes: CoachAttributes;
  career: CareerStint[];
  coach_id: string;
  name: string;
  nationality: string;
  personality: Personality;
  preferred_formation: string;
  style: "defensive" | "balanced" | "attacking";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "CoachAttributes".
 */
export interface CoachAttributes {
  in_game_adaptability: number;
  man_management: number;
  motivation: number;
  tactical_knowledge: number;
}
/**
 * Hidden traits. They never show on screen but shape how a player reacts to context.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Personality".
 */
export interface Personality {
  ambition: number;
  big_matches: number;
  consistency: number;
  controversy: number;
  injury_proneness: number;
  leadership: number;
  loyalty: number;
  pressure: number;
  professionalism: number;
  teamwork: number;
  temperament: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Competition".
 */
export interface Competition {
  competition_id: string;
  extra_time: boolean;
  importance: number;
  level: "league" | "domestic_cup" | "continental_club" | "international_tournament" | "friendly";
  name: string;
  neutral_venue: boolean;
  penalty_shootout: boolean;
  stage: "league" | "group" | "round_of_32" | "round_of_16" | "quarter_final" | "semi_final" | "final" | "friendly";
  tier: number;
}
/**
 * One modifier the simulator applied because of the context. Small by design (|delta| <= 0.15).
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "ContextEffect".
 */
export interface ContextEffect {
  delta: number;
  effect_id: string;
  note: string;
  source:
    | "former_club"
    | "former_teammate"
    | "former_coach"
    | "rivalry"
    | "competition"
    | "stakes"
    | "crowd"
    | "off_field"
    | "form"
    | "fatigue"
    | "weather"
    | "referee"
    | "head_to_head"
    | "injury";
  source_ref: string | null;
  subject_id: string;
  target:
    | "composure"
    | "motivation"
    | "concentration"
    | "fitness"
    | "aggression"
    | "chemistry"
    | "card_risk"
    | "error_rate"
    | "stamina_decay"
    | "injury_risk";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "DefendingAttributes".
 */
export interface DefendingAttributes {
  defensive_awareness: number;
  sliding_tackle: number;
  standing_tackle: number;
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
    | "recap.ready"
    | "player_stats.updated";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "ExplanationSentence".
 */
export interface ExplanationSentence {
  claims: Claim[];
  /**
   * @maxItems 3
   */
  context_ids: string[];
  /**
   * @minItems 1
   * @maxItems 4
   */
  evidence_ids: [string, ...string[]];
  text: string;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "FoulDetail".
 */
export interface FoulDetail {
  advantage_played: boolean;
  card: ("yellow" | "second_yellow" | "red") | null;
  card_reason:
    | (
        | "reckless_challenge"
        | "serious_foul_play"
        | "professional_foul"
        | "denying_goal_chance"
        | "handball"
        | "dissent"
        | "simulation"
        | "time_wasting"
        | "violent_conduct"
        | "persistent_fouling"
      )
    | null;
  foul_type:
    | "tackle"
    | "trip"
    | "push"
    | "hold"
    | "handball"
    | "dangerous_play"
    | "obstruction"
    | "simulation"
    | "dissent"
    | "time_wasting"
    | "off_the_ball";
  penalty_awarded: boolean;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "GoalkeepingAttributes".
 */
export interface GoalkeepingAttributes {
  diving: number;
  handling: number;
  kicking: number;
  positioning: number;
  reflexes: number;
}
/**
 * Record between the two clubs, counted from this match's home side.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "HeadToHead".
 */
export interface HeadToHead {
  away_wins: number;
  draws: number;
  home_wins: number;
  /**
   * @maxItems 10
   */
  last_meetings: PastMeeting[];
  played: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PastMeeting".
 */
export interface PastMeeting {
  away_club_id: string;
  away_goals: number;
  competition_id: string | null;
  home_club_id: string;
  home_goals: number;
  season: string;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "HeatGrid".
 */
export interface HeatGrid {
  cells: number[];
  samples: number;
}
/**
 * GET /api/matches/{id}/heatmaps: where each team and player spent their time.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "HeatmapReport".
 */
export interface HeatmapReport {
  cols: number;
  match_id: string;
  period: (1 | 2 | 3 | 4 | 5) | null;
  players: PlayerHeat[];
  rows: number;
  source: "frames" | "events";
  teams: {
    [k: string]: HeatGrid;
  };
  up_to_t: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PlayerHeat".
 */
export interface PlayerHeat {
  cells: number[];
  player_id: string;
  samples: number;
  team: "home" | "away";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "InjuryInfo".
 */
export interface InjuryInfo {
  area: "hamstring" | "groin" | "thigh" | "knee" | "ankle" | "calf" | "foot" | "back" | "shoulder" | "head" | "other";
  can_continue: boolean;
  cause: "contact" | "non_contact" | "fatigue";
  expected_days_out: number;
  severity: "knock" | "minor" | "moderate" | "serious";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "LineupSlot".
 */
export interface LineupSlot {
  /**
   * @minItems 2
   * @maxItems 2
   */
  anchor: [number, number];
  player_id: string;
  role: "GK" | "LB" | "CB" | "RB" | "LWB" | "RWB" | "DM" | "CM" | "AM" | "LM" | "RM" | "LW" | "RW" | "ST";
  slot: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Match".
 */
export interface Match {
  away: Team;
  clock: number;
  context: MatchContext;
  decided_by: ("normal_time" | "extra_time" | "penalties") | null;
  home: Team;
  match_id: string;
  period: 1 | 2 | 3 | 4 | 5;
  periods: PeriodInfo[];
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
  club_id: string;
  coach: Coach;
  color: string;
  name: string;
  sheet: TeamSheet;
  short_name: string;
  side: "home" | "away";
  squad: Player[];
  tactics: TeamTactics;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "TeamSheet".
 */
export interface TeamSheet {
  /**
   * @maxItems 15
   */
  bench: string[];
  captain_id: string;
  corner_taker_left_id: string;
  corner_taker_right_id: string;
  formation: string;
  free_kick_taker_id: string;
  penalty_taker_id: string;
  /**
   * @minItems 7
   * @maxItems 11
   */
  starters: [LineupSlot, LineupSlot, LineupSlot, LineupSlot, LineupSlot, LineupSlot, LineupSlot, ...LineupSlot[]];
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Player".
 */
export interface Player {
  age: number;
  attributes: PlayerAttributes;
  career: CareerStint[];
  height_cm: number;
  name: string;
  nationality: string;
  personality: Personality;
  player_id: string;
  /**
   * Broad position group derived from `role`.
   */
  position: "GK" | "DF" | "MF" | "FW";
  preferred_foot: "left" | "right";
  role: "GK" | "LB" | "CB" | "RB" | "LWB" | "RWB" | "DM" | "CM" | "AM" | "LM" | "RM" | "LW" | "RW" | "ST";
  secondary_roles: (
    "GK" | "LB" | "CB" | "RB" | "LWB" | "RWB" | "DM" | "CM" | "AM" | "LM" | "RM" | "LW" | "RW" | "ST"
  )[];
  shirt_number: number;
  skill_moves: number;
  team: "home" | "away";
  traits: (
    | "finesse_shot"
    | "power_shot"
    | "dead_ball"
    | "chip_shot"
    | "acrobatic"
    | "incisive_pass"
    | "long_ball_pass"
    | "whipped_cross"
    | "tiki_taka"
    | "rapid"
    | "quick_step"
    | "technical"
    | "trickster"
    | "first_touch"
    | "press_proven"
    | "intercept"
    | "block"
    | "bruiser"
    | "slide_tackle"
    | "aerial"
    | "relentless"
    | "long_throw"
    | "leader"
  )[];
  weak_foot: number;
  weight_kg: number;
  work_rate_attack: "low" | "medium" | "high";
  work_rate_defence: "low" | "medium" | "high";
}
/**
 * 34 visible ratings in seven groups. The simulator reads these directly.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PlayerAttributes".
 */
export interface PlayerAttributes {
  attacking: AttackingAttributes;
  defending: DefendingAttributes;
  goalkeeping: GoalkeepingAttributes;
  mentality: MentalityAttributes;
  movement: MovementAttributes;
  power: PowerAttributes;
  skill: SkillAttributes;
  summary: AttributeSummary1;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "MentalityAttributes".
 */
export interface MentalityAttributes {
  aggression: number;
  attack_positioning: number;
  composure: number;
  interceptions: number;
  penalties: number;
  vision: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "MovementAttributes".
 */
export interface MovementAttributes {
  acceleration: number;
  agility: number;
  balance: number;
  reactions: number;
  sprint_speed: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PowerAttributes".
 */
export interface PowerAttributes {
  jumping: number;
  long_shots: number;
  shot_power: number;
  stamina: number;
  strength: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "SkillAttributes".
 */
export interface SkillAttributes {
  ball_control: number;
  curve: number;
  dribbling: number;
  free_kick_accuracy: number;
  long_passing: number;
}
/**
 * Six headline ratings, weighted from the detailed ones (an approximation of game cards).
 */
export interface AttributeSummary1 {
  defending: number;
  dribbling: number;
  pace: number;
  passing: number;
  physical: number;
  shooting: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "TeamTactics".
 */
export interface TeamTactics {
  attack_focus: "left" | "centre" | "right" | "balanced";
  counter_attack: boolean;
  instructions: PlayerInstruction[];
  line_height: "low" | "mid" | "high";
  offside_trap: boolean;
  passing: "short" | "mixed" | "direct";
  press: "low" | "mid" | "high";
  set_pieces: SetPieceTactics;
  tempo: "slow" | "normal" | "fast";
  time_wasting: boolean;
  width: "narrow" | "normal" | "wide";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PlayerInstruction".
 */
export interface PlayerInstruction {
  instruction:
    | "stay_back"
    | "get_forward"
    | "overlap"
    | "underlap"
    | "cut_inside"
    | "stay_wide"
    | "roam"
    | "hold_position"
    | "press_more"
    | "sit_deeper"
    | "man_mark";
  player_id: string;
  target_player_id: string | null;
}
export interface SetPieceTactics {
  corner_defence: "zonal" | "man" | "mixed";
  corner_delivery: "inswing" | "outswing" | "short" | "mixed";
  corner_target: "near_post" | "far_post" | "penalty_spot" | "edge_of_box" | "mixed";
  free_kick_style: "direct" | "cross" | "short" | "mixed";
  players_back_on_corners: number;
  players_forward_on_corners: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "MatchContext".
 */
export interface MatchContext {
  attendance: number;
  competition: Competition;
  conditions: PreMatchCondition[];
  derby: boolean;
  effects: ContextEffect[];
  /**
   * @maxItems 2
   */
  form: TeamForm[];
  head_to_head: HeadToHead | null;
  news: OffFieldEvent[];
  pitch: "good" | "worn" | "heavy" | "artificial";
  referee: Referee | null;
  relationships: Relationship[];
  stakes: "none" | "title_race" | "relegation" | "qualification" | "knockout";
  venue: string;
  weather: "clear" | "rain" | "wind" | "heat" | "snow";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PreMatchCondition".
 */
export interface PreMatchCondition {
  availability: "available" | "injured" | "suspended" | "ill" | "not_selected";
  carrying_knock: boolean;
  days_since_last_match: number | null;
  fitness: number;
  injury: InjuryInfo | null;
  morale: number;
  on_yellow_card_threshold: boolean;
  player_id: string;
  /**
   * @maxItems 5
   */
  recent_ratings: number[];
  sharpness: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "TeamForm".
 */
export interface TeamForm {
  goals_against_last5: number;
  goals_for_last5: number;
  /**
   * @maxItems 5
   */
  last_results: ("W" | "D" | "L")[];
  league_position: number | null;
  points: number | null;
  side: "home" | "away";
}
/**
 * A fictional news item about a player or coach before the match.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "OffFieldEvent".
 */
export interface OffFieldEvent {
  headline: string;
  hours_before_kickoff: number;
  kind:
    | "nightlife"
    | "late_return"
    | "family_matter"
    | "contract_dispute"
    | "transfer_rumour"
    | "public_criticism"
    | "fan_conflict"
    | "training_ground_clash"
    | "disciplinary"
    | "illness"
    | "charity"
    | "milestone"
    | "new_contract";
  news_id: string;
  public: boolean;
  sentiment: "negative" | "neutral" | "positive";
  severity: number;
  subject_id: string;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Referee".
 */
export interface Referee {
  advantage_tendency: number;
  big_match_experience: number;
  card_tendency: number;
  name: string;
  referee_id: string;
  strictness: number;
}
/**
 * A tie between two people that can matter on match day (chemistry, motivation, needle).
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Relationship".
 */
export interface Relationship {
  kind:
    "former_teammate" | "former_coach" | "former_player" | "mentor" | "friend" | "rival" | "feud" | "national_teammate";
  other_id: string;
  person_id: string;
  relationship_id: string;
  sentiment: number;
  shared_seasons: number;
}
/**
 * When each period started and ended on the elapsed clock, so any `t` can be labelled.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PeriodInfo".
 */
export interface PeriodInfo {
  added_minutes: number | null;
  end_t: number | null;
  period: 1 | 2 | 3 | 4 | 5;
  start_t: number;
}
export interface Score {
  away: number;
  away_penalties: number | null;
  home: number;
  home_penalties: number | null;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "MatchAnalysis".
 */
export interface MatchAnalysis {
  deserved: AnalysisDeserved;
  game_state: AnalysisGameState[];
  lanes: {
    [k: string]: {
      [k: string]: AnalysisLane;
    };
  };
  match_id: string;
  phases: AnalysisPhase[];
  profile: AnalysisProfile;
  rolling: AnalysisRolling[];
  shot_quality: {
    [k: string]: AnalysisShotQuality;
  };
  subs: AnalysisSub[];
  up_to_t: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "MatchEvent".
 */
export interface MatchEvent {
  added_minutes: number | null;
  /**
   * Penalty or six-yard box `location` falls in, if any, from the acting team's view.
   */
  area: ("own_six_yard_box" | "own_box" | "opp_box" | "opp_six_yard_box" | "open") | null;
  ball_speed_kmh: number | null;
  body_part: ("left_foot" | "right_foot" | "head" | "other") | null;
  /**
   * What a broadcast would show: 63', 45+2', 105+1', or PEN in the shootout.
   */
  clock_label: string;
  counterpress: boolean;
  deflected: boolean;
  delivery: ("inswing" | "outswing" | "straight") | null;
  duel_type: ("aerial" | "ground") | null;
  end_location: [number, number] | null;
  event_id: string;
  first_time: boolean;
  foul: FoulDetail | null;
  /**
   * Threat-grid zone of `location`.
   */
  from_zone: [number, number] | null;
  injury: InjuryInfo | null;
  keeper_action:
    | (
        | "shot_saved"
        | "shot_parried"
        | "tipped_over"
        | "goal_conceded"
        | "claim"
        | "punch"
        | "sweep"
        | "smother"
        | "pick_up"
      )
    | null;
  keeper_location: [number, number] | null;
  keeper_technique: ("standing" | "diving" | "reflex") | null;
  /**
   * Vertical lane of `location` (wings, half-spaces, centre), from the acting team's view.
   */
  lane: ("left_wing" | "left_half_space" | "centre" | "right_half_space" | "right_wing") | null;
  location: [number, number] | null;
  match_id: string;
  meta: {
    [k: string]: string;
  };
  /**
   * Elapsed match minute (0-based, stoppage and extra time included): t // 60.
   */
  minute: number;
  outcome: ("success" | "fail") | null;
  pass_height: ("ground" | "low" | "high") | null;
  pass_technique: ("normal" | "chip" | "flick_on" | "lay_off" | "backheel" | "outside_foot") | null;
  pass_type:
    | (
        | "regular"
        | "cross"
        | "through_ball"
        | "switch"
        | "cutback"
        | "long_ball"
        | "back_pass"
        | "corner"
        | "free_kick"
        | "throw_in"
        | "goal_kick"
        | "kick_off"
        | "keeper_throw"
        | "keeper_kick"
      )
    | null;
  period: 1 | 2 | 3 | 4 | 5;
  period_t: number;
  play_pattern:
    ("open_play" | "counter" | "corner" | "free_kick" | "throw_in" | "goal_kick" | "kick_off" | "penalty") | null;
  player_id: string | null;
  possession_id: number | null;
  receiver_id: string | null;
  related_event_ids: string[];
  schema_version: 1;
  seq: number;
  shootout_round: number | null;
  shot_end_height_m: number | null;
  shot_outcome: ("goal" | "saved" | "off_target" | "blocked" | "post" | "disallowed") | null;
  shot_technique: ("normal" | "volley" | "half_volley" | "lob" | "backheel" | "diving_header" | "overhead_kick") | null;
  substitution: Substitution | null;
  success_prob: number | null;
  t: number;
  tactics: TeamTactics | null;
  team: "home" | "away";
  team_sheet: TeamSheet | null;
  /**
   * Pitch third of `location`, from the acting team's point of view.
   */
  third: ("defensive" | "middle" | "final") | null;
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
    | "goalkeeper"
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
    | "var_review"
    | "injury"
    | "substitution"
    | "tactical_shift"
    | "kickoff"
    | "added_time"
    | "period_end";
  under_pressure: boolean;
  var: VarReview | null;
  xg: number | null;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Substitution".
 */
export interface Substitution {
  player_off_id: string;
  player_on_id: string;
  reason: "tactical" | "fatigue" | "injury" | "card_risk" | "time_wasting";
  slot: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "VarReview".
 */
export interface VarReview {
  decision: "confirmed" | "overturned";
  duration_s: number;
  reason:
    | "offside"
    | "handball"
    | "foul_in_build_up"
    | "ball_out_of_play"
    | "no_foul"
    | "foul_confirmed"
    | "wrong_player"
    | "clear_and_obvious_error";
  review_of: "goal" | "penalty" | "red_card" | "mistaken_identity";
  reviewed_event_id: string;
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
 * Result after 90 minutes, plus who goes through when extra time and penalties apply.
 *
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
  home_advance: number | null;
  home_win: number;
}
/**
 * A confirmed pivot as a lower-third card, timed on the match clock (FR-26).
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "OverlayCard".
 */
export interface OverlayCard {
  direction: "home" | "away";
  direction_team: string;
  headline: string;
  hide_at: number;
  minute: number;
  minute_label: string;
  pivot_id: string;
  severity: 1 | 2 | 3;
  show_at: number;
  status: "confirmed" | "degraded";
  subline: string | null;
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
  kind: "pivot" | "goal" | "card" | "substitution" | "var_review" | "injury" | "player_rating";
  overlay_id: string;
  player_id: string | null;
  ref_id: string;
  severity: (1 | 2 | 3) | null;
  show_at: number;
  subline: string | null;
  team: "home" | "away";
}
/**
 * What the overlay shows at one moment of the match clock: the score bug and at most one card.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "OverlayFrame".
 */
export interface OverlayFrame {
  card: OverlayCard | null;
  clock: number;
  match_id: string;
  scoreboard: OverlayScoreboard;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "OverlayScoreboard".
 */
export interface OverlayScoreboard {
  away_short: string;
  clock_label: string;
  home_short: string;
  period: 1 | 2 | 3 | 4 | 5;
  score: Score1;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "Score".
 */
export interface Score1 {
  away: number;
  away_penalties: number | null;
  home: number;
  home_penalties: number | null;
}
/**
 * Every card of a match in clock order, never overlapping, for recordings and the preview page.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "OverlayTimeline".
 */
export interface OverlayTimeline {
  card_seconds: number;
  cards: OverlayCard[];
  match_id: string;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PassNetworkEdge".
 */
export interface PassNetworkEdge {
  from_id: string;
  passes: number;
  to_id: string;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PassNetworkNode".
 */
export interface PassNetworkNode {
  passes: number;
  player_id: string;
  received: number;
  x: number;
  y: number;
}
/**
 * GET /api/matches/{id}/pass-network: each side's starting eleven and who passed to whom.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PassNetworkReport".
 */
export interface PassNetworkReport {
  match_id: string;
  min_passes: number;
  period: (1 | 2 | 3 | 4 | 5) | null;
  teams: {
    [k: string]: TeamPassNetwork;
  };
  up_to_t: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "TeamPassNetwork".
 */
export interface TeamPassNetwork {
  edges: PassNetworkEdge[];
  nodes: PassNetworkNode[];
  source: "frames" | "events";
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
  type: "red_card" | "substitution" | "goal" | "press_change" | "formation_change" | "injury";
}
/**
 * One player's line for this match, updated live, like the ratings in score apps.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PlayerMatchStats".
 */
export interface PlayerMatchStats {
  aerials_won: number;
  assists: number;
  distance_km: number;
  dribbles_won: number;
  duels_won: number;
  fouls_committed: number;
  goals: number;
  interceptions: number;
  key_passes: number;
  match_id: string;
  minutes_played: number;
  pass_accuracy_pct: number | null;
  passes: number;
  player_id: string;
  progressive_passes: number;
  rating: number;
  saves: number;
  shots: number;
  sprints: number;
  tackles_won: number;
  top_speed_kmh: number;
  up_to_t: number;
  xa: number;
  xg: number;
}
/**
 * A turning point a player took part in.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PlayerPivotLink".
 */
export interface PlayerPivotLink {
  event_ids: string[];
  in_trigger: boolean;
  minute: number;
  pivot_id: string;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PlayerPosition".
 */
export interface PlayerPosition {
  fitness: number;
  player_id: string;
  speed_ms: number;
  x: number;
  y: number;
}
/**
 * What the page can show about one player, up to a point in the match (focus-player card).
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PlayerReport".
 */
export interface PlayerReport {
  event_ids: string[];
  name: string;
  pivots: PlayerPivotLink[];
  player_id: string;
  role: string;
  shirt_number: number;
  stats: PlayerMatchStats | null;
  team: "home" | "away";
}
/**
 * GET /api/matches/{id}/players/stats: every player of both squads, or the one asked for.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PlayerStatsReport".
 */
export interface PlayerStatsReport {
  match_id: string;
  players: PlayerReport[];
  source: "stored" | "computed";
  up_to_t: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchFixture".
 */
export interface PrematchFixture {
  competition: string;
  days_until: number;
  fictional: boolean;
  importance: "low" | "medium" | "high";
  matchday: number | null;
  opponent: string;
  opponent_id: string;
  rotation_note: string;
  rotation_note_key: string;
  rotation_params: {
    [k: string]: string | number;
  };
  rotation_risk: "low" | "medium" | "high";
  stage: string | null;
  venue: "H" | "A";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchFormStats".
 */
export interface PrematchFormStats {
  avg_rating: number | null;
  btts: number;
  clean_sheets: number;
  conceded_by_period: {
    [k: string]: number;
  };
  failed_to_score: number;
  ga_avg: number;
  games: number;
  gf_avg: number;
  goals_by_period: {
    [k: string]: number;
  };
  ht_lead_dropped: number;
  ht_lead_won: number;
  over_2_5: number;
  reds: number;
  scored_first: number;
}
/**
 * One recent league game, seen from the team: `ft` and `ht` are [this team, opponent].
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchGame".
 */
export interface PrematchGame {
  came_from_behind: boolean;
  /**
   * @minItems 2
   * @maxItems 2
   */
  ft: [number, number];
  /**
   * @minItems 2
   * @maxItems 2
   */
  ht: [number, number];
  matchday: number;
  opponent: string;
  opponent_id: string;
  result: "W" | "D" | "L";
  scored_first: boolean;
  season: number;
  venue: "H" | "A";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchH2HCount".
 */
export interface PrematchH2HCount {
  away_w: number;
  d: number;
  home_w: number;
  played: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchHeadToHead".
 */
export interface PrematchHeadToHead {
  all: PrematchH2HCount;
  at_this_ground: PrematchH2HCount;
  meetings: PrematchMeeting[];
}
/**
 * `ft` and `ht` are [home, away] of that meeting.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchMeeting".
 */
export interface PrematchMeeting {
  away_club: string;
  /**
   * @minItems 2
   * @maxItems 2
   */
  ft: [number, number];
  home_club: string;
  /**
   * @minItems 2
   * @maxItems 2
   */
  ht: [number, number];
  matchday: number;
  season: number;
  venue_club: string;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchLine".
 */
export interface PrematchLine {
  away: string[];
  away_players: string[];
  home: string[];
  home_players: string[];
  note: string;
  note_key: string;
  params: {
    [k: string]: string | number;
  };
  zone: "home_wide_left" | "home_wide_right" | "midfield" | "home_attack" | "away_attack";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchMatchup".
 */
export interface PrematchMatchup {
  away_formation: string;
  home_formation: string;
  lines: PrematchLine[];
  perspective: "home" | "away";
  tactics_diff: PrematchTacticsDiff[];
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchTacticsDiff".
 */
export interface PrematchTacticsDiff {
  away: string;
  field: string;
  home: string;
  note: string;
  note_key: string;
  params: {
    [k: string]: string | number;
  };
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchRecord".
 */
export interface PrematchRecord {
  d: number;
  ga: number;
  gf: number;
  l: number;
  played: number;
  position: number | null;
  ppg: number;
  pts: number;
  w: number;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchReport".
 */
export interface PrematchReport {
  about: string;
  about_key: string;
  head_to_head: PrematchHeadToHead;
  match_id: string;
  matchday: number;
  matchup: PrematchMatchup;
  season: number;
  teams: {
    [k: string]: PrematchTeam;
  };
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchTeam".
 */
export interface PrematchTeam {
  away_only: PrematchRecord;
  club_id: string;
  home_only: PrematchRecord;
  last5: PrematchGame[];
  last5_stats: PrematchFormStats;
  name: string;
  next_fixture: PrematchFixture | null;
  next_league: PrematchFixture | null;
  overall: PrematchRecord;
  usual_xi_today: PrematchUsualXi;
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchUsualXi".
 */
export interface PrematchUsualXi {
  games: number;
  newcomers: string[];
  regulars: string[];
  regulars_benched: string[];
  regulars_starting: number;
  usual_xi_named: boolean;
}
/**
 * `texts`: each English sentence of the pre-match tab that has a translation, and that translation.
 * A sentence missing here is shown in English. `untranslated` lists those sentences.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "PrematchText".
 */
export interface PrematchText {
  lang: string;
  match_id: string;
  texts: {
    [k: string]: string;
  };
  untranslated: string[];
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
  baseline_stats?: ArmStats | null;
  counterfactual: OutcomeDist;
  counterfactual_stats?: ArmStats | null;
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
  tactics: TeamTactics | null;
  target_event_id: string | null;
  team: ("home" | "away") | null;
  team_sheet: TeamSheet | null;
  type:
    | "cancel_substitution"
    | "move_substitution"
    | "remove_red_card"
    | "remove_goal"
    | "change_press"
    | "change_formation"
    | "change_tactics"
    | "change_lineup";
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "SetPieceTactics".
 */
export interface SetPieceTactics1 {
  corner_defence: "zonal" | "man" | "mixed";
  corner_delivery: "inswing" | "outswing" | "short" | "mixed";
  corner_target: "near_post" | "far_post" | "penalty_spot" | "edge_of_box" | "mixed";
  free_kick_style: "direct" | "cross" | "short" | "mixed";
  players_back_on_corners: number;
  players_forward_on_corners: number;
}
/**
 * GET /api/matches/{id}/shots: every shot so far (the shootout left out).
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "ShotMap".
 */
export interface ShotMap {
  match_id: string;
  period: (1 | 2 | 3 | 4 | 5) | null;
  shots: ShotMapShot[];
  up_to_t: number;
}
/**
 * One shot: where from and where to, from the shooter's side, the goal they attack at x = 105.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "ShotMapShot".
 */
export interface ShotMapShot {
  body_part: ("left_foot" | "right_foot" | "head" | "other") | null;
  clock_label: string;
  end_x: number | null;
  end_y: number | null;
  event_id: string;
  first_time: boolean;
  outcome: ("goal" | "saved" | "off_target" | "blocked" | "post" | "disallowed") | null;
  period: 1 | 2 | 3 | 4 | 5;
  play_pattern:
    ("open_play" | "counter" | "corner" | "free_kick" | "throw_in" | "goal_kick" | "kick_off" | "penalty") | null;
  player_id: string | null;
  t: number;
  team: "home" | "away";
  technique: ("normal" | "volley" | "half_volley" | "lob" | "backheel" | "diving_header" | "overhead_kick") | null;
  under_pressure: boolean;
  x: number;
  xg: number | null;
  y: number;
}
/**
 * How the page labels one stat, so it hard-codes nothing (the D02 vocabulary, MET-001 to MET-023).
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "StatMetricInfo".
 */
export interface StatMetricInfo {
  decimals: number;
  definition_id: string;
  description: string;
  fan_label: string;
  group: "attack" | "possession" | "defence" | "shape" | "physical";
  higher_means: string;
  label: string;
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
    | "distance_covered_km"
    | "progressive_passes"
    | "ppda"
    | "xa"
    | "field_tilt_pct";
  unit: "count" | "pct" | "xg" | "index" | "m" | "km" | "ratio";
}
/**
 * GET /api/matches/{id}/stats: the 23 team stats per part of the match, with their labels.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "TeamStatsReport".
 */
export interface TeamStatsReport {
  match_id: string;
  metrics: StatMetricInfo[];
  scopes: TeamStatsScope[];
  up_to_t: number;
}
/**
 * Both teams' stats for one part of the match. A stat with no answer is null, never 0.
 *
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "TeamStatsScope".
 */
export interface TeamStatsScope {
  away: {
    [k: string]: number | null;
  };
  home: {
    [k: string]: number | null;
  };
  period: (1 | 2 | 3 | 4 | 5) | null;
  scope: "match" | "first_half" | "second_half" | "extra_time_1" | "extra_time_2" | "window";
  /**
   * @minItems 2
   * @maxItems 2
   */
  window: [number, number];
}
/**
 * This interface was referenced by `Pivot`'s JSON-Schema
 * via the `definition` "TrackingFrame".
 */
export interface TrackingFrame {
  ball: BallPosition;
  match_id: string;
  period: 1 | 2 | 3 | 4 | 5;
  /**
   * @maxItems 22
   */
  players: PlayerPosition[];
  possession: ("home" | "away") | null;
  t: number;
}
