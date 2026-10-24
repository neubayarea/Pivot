// Front-end stand-in for the demo-1021 preset, used by S1 until C03 wires the real API.
// Not the official B02 fixture: everything here is generated from a fixed seed so the
// board replays identically every time. Types follow @pivot/contracts exactly.
import type {
  Claim,
  ExplanationSentence,
  MatchEvent,
  MinuteMetric,
  Pivot1 as Pivot,
  Team,
  ViewerPrefs,
} from "@pivot/contracts";
import { buildPivotDetails, momentumAvg, type BeforeAfterRow, type PivotDetailData } from "./pivot-detail";

export const MATCH_ID = "demo-1021";

type Side = "home" | "away";
export type TeamInfo = Pick<Team, "name" | "short_name" | "side" | "color">;

/** A pivot plus when (match seconds) the pipeline flags it and when the verifier signs it off. */
export type PivotTimeline = { pivot: Pivot; pendingAt: number; confirmedAt: number };

export type MatchFixture = {
  matchId: string;
  teams: Record<Side, TeamInfo>;
  players: Record<string, string>;
  events: MatchEvent[];
  metrics: MinuteMetric[];
  pivots: PivotTimeline[];
  /** S2 data per pivot: the timeline window, per-second positions and the before/after table. */
  details: Record<string, PivotDetailData>;
  /** Match second the replay starts from, just before the 74′ pivot is flagged. */
  startAt: number;
  endAt: number;
};

const TEAMS: Record<Side, TeamInfo> = {
  home: { name: "Harbour City", short_name: "HCY", side: "home", color: "#1C2C6E" },
  away: { name: "Northvale Rovers", short_name: "NVR", side: "away", color: "#D22B3C" },
};

export const ROSTER: Record<Side, [string, string][]> = {
  home: [
    ["hcy-1", "K. Doyle"], ["hcy-4", "J. Kessler"], ["hcy-5", "M. Lund"], ["hcy-6", "S. Haddad"],
    ["hcy-8", "L. Varga"], ["hcy-10", "P. Reyes"], ["hcy-11", "A. Moreau"], ["hcy-14", "O. Brandt"],
    ["hcy-9", "D. Okafor"], ["hcy-7", "C. Nkemelu"], ["hcy-3", "E. Silva"], ["hcy-17", "F. Rossi"],
  ],
  away: [
    ["nvr-1", "H. Quinn"], ["nvr-2", "B. Holm"], ["nvr-5", "G. Petrov"], ["nvr-6", "N. Ward"],
    ["nvr-4", "E. Castro"], ["nvr-8", "K. Ansah"], ["nvr-10", "R. Ibe"], ["nvr-7", "I. Sato"],
    ["nvr-11", "V. Mensah"], ["nvr-3", "L. Achterberg"], ["nvr-9", "T. Marsh"],
  ],
};
const PLAYERS = Object.fromEntries([...ROSTER.home, ...ROSTER.away]);

// Who is on the pitch at a given second: Petrov is sent off at 37:52, Rossi replaces Moreau at 62:40.
const RED_AT = 37 * 60 + 52;
const SUB_AT = 62 * 60 + 40;
function onPitch(team: Side, t: number, keepers = false): string[] {
  return ROSTER[team]
    .map(([id]) => id)
    .filter((id) => {
      if (id === "hcy-17") return t >= SUB_AT;
      if (id === "hcy-11") return t < SUB_AT;
      if (id === "nvr-5") return t < RED_AT;
      return keepers || !id.endsWith("-1"); // keepers stay out of the open-play feed
    });
}

// Park–Miller generator, same seed as the design spec's momentum sample.
let seed = 1021;
function rnd(): number {
  seed = (seed * 16807) % 2147483647;
  return seed / 2147483647;
}
const pick = <T,>(xs: readonly T[]): T => xs[Math.floor(rnd() * xs.length)];

// ---------- Momentum: home above zero, away below; resets at half time ----------
function momentumTarget(minute: number): number {
  if (minute < 38) return 0.05;
  if (minute < 63) return 0.45;
  if (minute < 74) return -0.4;
  return 0.3;
}
const metrics: MinuteMetric[] = [];
for (let minute = 0, v = 0; minute <= 90; minute++) {
  if (minute === 0 || minute === 46) v = 0;
  else v = Math.max(-1, Math.min(1, v + (momentumTarget(minute) - v) * 0.16 + (rnd() - 0.5) * 0.22));
  const home = Math.max(0, v);
  const away = Math.max(0, -v);
  metrics.push({
    match_id: MATCH_ID,
    minute,
    momentum: Math.round(v * 1000) / 1000,
    threat_home: Math.round((0.2 + home * 0.8) * 100) / 100,
    threat_away: Math.round((0.2 + away * 0.8) * 100) / 100,
    pressure_home: Math.round((0.3 + away * 0.6) * 100) / 100,
    pressure_away: Math.round((0.3 + home * 0.6) * 100) / 100,
  });
}

// ---------- Events ----------
const pad = (n: number) => String(n).padStart(2, "0");
export const clockLabel = (t: number) => `${pad(Math.floor(t / 60))}:${pad(Math.floor(t % 60))}`;

const events: MatchEvent[] = [];
function push(team: Side, t: number, type: MatchEvent["type"], extra: Partial<MatchEvent> = {}): MatchEvent {
  const period = t < 45 * 60 ? 1 : 2;
  const e: MatchEvent = {
    added_minutes: null, area: null, ball_speed_kmh: null, body_part: null,
    clock_label: clockLabel(t), end_location: null, event_id: "", from_zone: null, lane: null,
    location: null, match_id: MATCH_ID, meta: {}, minute: Math.floor(t / 60), outcome: null,
    pass_height: null, pass_type: null, period, period_t: period === 1 ? t : t - 45 * 60,
    play_pattern: null, player_id: null, possession_id: null, receiver_id: null, related_event_ids: [],
    schema_version: 1, seq: 0, shootout_round: null, shot_end_height_m: null, shot_outcome: null,
    substitution: null, success_prob: null, t, tactics: null, team, team_sheet: null, third: null,
    threat: 0, to_zone: null, type, under_pressure: false, xg: null,
    // Fields added to the data format after B01 was first merged (PR #71).
    counterpress: false, deflected: false, delivery: null, duel_type: null, first_time: false,
    foul: null, injury: null, keeper_action: null, keeper_location: null, keeper_technique: null,
    pass_technique: null, shot_technique: null, var: null,
    ...extra,
  };
  events.push(e);
  return e;
}

// Scripted moments the pivots hang on.
const SCRIPT: [number, Side, MatchEvent["type"], Partial<MatchEvent>][] = [
  [0, "home", "kickoff", { player_id: "hcy-9", play_pattern: "kick_off" }],
  [RED_AT, "away", "card", { player_id: "nvr-5", meta: { card: "red" } }],
  [41 * 60 + 18, "home", "shot", { player_id: "hcy-9", shot_outcome: "goal", xg: 0.34, area: "opp_box", body_part: "right_foot", third: "final", threat: 0.9 }],
  [45 * 60, "home", "period_end", {}],
  [45 * 60 + 1, "away", "kickoff", { player_id: "nvr-9", play_pattern: "kick_off" }],
  [SUB_AT, "home", "substitution", { player_id: "hcy-11", substitution: { player_off_id: "hcy-11", player_on_id: "hcy-17", reason: "fatigue", slot: 7 } }],
  [70 * 60 + 6, "away", "shot", { player_id: "nvr-9", shot_outcome: "goal", xg: 0.27, area: "opp_box", body_part: "head", third: "final", threat: 0.85 }],
  [73 * 60 + 20, "home", "tactical_shift", { meta: { note: "Back three" } }],
  [86 * 60 + 44, "home", "shot", { player_id: "hcy-17", shot_outcome: "goal", xg: 0.41, area: "opp_box", body_part: "left_foot", third: "final", threat: 0.92 }],
  [90 * 60, "home", "period_end", {}],
];

const OPEN_PLAY: [MatchEvent["type"], number][] = [
  ["pass", 0.55], ["pressure", 0.15], ["carry", 0.07], ["duel", 0.07], ["tackle", 0.05],
  ["interception", 0.04], ["shot", 0.035], ["clearance", 0.035],
];
function openPlayType(): MatchEvent["type"] {
  let r = rnd();
  for (const [type, p] of OPEN_PLAY) if ((r -= p) < 0) return type;
  return "pass";
}

let next = 0;
function flushScript(upTo: number) {
  for (; next < SCRIPT.length && SCRIPT[next][0] <= upTo; next++) {
    const [st, team, type, extra] = SCRIPT[next];
    push(team, st, type, extra);
  }
}
for (let t = 5; t < 90 * 60; t += 6 + Math.floor(rnd() * 9)) {
  flushScript(t);
  if (Math.abs(t - 45 * 60) < 20) continue;
  const m = metrics[Math.floor(t / 60)].momentum;
  const team: Side = rnd() < 0.5 + 0.28 * m ? "home" : "away";
  const opp: Side = team === "home" ? "away" : "home";
  const type = openPlayType();
  // Pressing is done by the side without the ball, so it follows the other team's momentum.
  const actor: Side = type === "pressure" ? opp : team;
  const player_id = pick(onPitch(actor, t));
  const ok: MatchEvent["outcome"] = rnd() < 0.78 ? "success" : "fail";
  const third = pick(["defensive", "middle", "middle", "final"] as const);
  if (type === "pass") {
    const corner = third === "final" && rnd() < 0.06;
    push(actor, t, "pass", {
      player_id, outcome: ok, third, pass_type: corner ? "corner" : "regular",
      receiver_id: ok === "success" ? pick(onPitch(actor, t).filter((p) => p !== player_id)) : null,
      meta: corner ? { side: rnd() < 0.5 ? "left" : "right" } : {},
    });
  } else if (type === "shot") {
    push(actor, t, "shot", {
      player_id, third: "final", area: "opp_box", xg: Math.round((0.03 + rnd() * 0.18) * 100) / 100,
      shot_outcome: pick(["saved", "off_target", "off_target", "blocked"] as const),
    });
  } else {
    push(actor, t, type, { player_id, outcome: type === "pressure" ? null : ok, third });
  }
}
flushScript(Infinity);
events.sort((a, b) => a.t - b.t);
events.forEach((e, i) => {
  e.seq = 2000 + i;
  e.event_id = `ev-${e.seq}`;
});

// ---------- Pivots ----------
const PREFS: ViewerPrefs = { audience: "analyst", language: "en", focus_team: null, focus_player_id: null };
const inWindow = (from: number, to: number, f: (e: MatchEvent) => boolean, n: number) =>
  events.filter((e) => e.t >= from * 60 && e.t < to * 60 && f(e)).slice(0, n).map((e) => e.event_id);
const evidence = (ids: string[]) => ids as [string, ...string[]];
const at = (type: MatchEvent["type"], t: number) => events.find((e) => e.type === type && e.t === t)!.event_id;

function sentence(text: string, ids: string[], claims: ExplanationSentence["claims"] = []): ExplanationSentence {
  return { text, evidence_ids: evidence(ids), claims, context_ids: [] };
}
const claim = (metric: ExplanationSentence["claims"][number]["stat_ref"]["metric"], team: Side,
  window: [number, number], value: number, unit: ExplanationSentence["claims"][number]["unit"] = "count") =>
  ({ stat_ref: { metric, team, player_id: null, window }, unit, value });

function pivot(id: string, minute: number, direction: Side, severity: Pivot["severity"], triggers: string[],
  headline: string, sentences: ExplanationSentence[]): Pivot {
  return {
    pivot_id: id, chain_id: `chain-${id}`, match_id: MATCH_ID, minute, direction, severity, status: "confirmed",
    trigger_event_ids: triggers,
    narrative: { chain_id: `chain-${id}`, headline, prefs: PREFS, source: "llm", verifier_attempts: 1,
      sentences: sentences as [ExplanationSentence, ...ExplanationSentence[]] },
  };
}

const red = at("card", RED_AT);
const sub = at("substitution", SUB_AT);
const shift = at("tactical_shift", 73 * 60 + 20);
const goal = (t: number) => at("shot", t);

const pivots: PivotTimeline[] = [
  {
    pendingAt: 38 * 60 + 30, confirmedAt: 39 * 60 + 40,
    pivot: pivot("pv-38", 38, "home", 3, [red], "Red card tilted control to Harbour City", [
      sentence("Petrov's red card left Northvale with ten men for the last 52 minutes.", [red]),
      sentence("Harbour City's possession rose from 48% to 61% in the ten minutes after the dismissal.",
        inWindow(38, 48, (e) => e.team === "home" && e.type === "pass", 2), [claim("possession_pct", "home", [38, 48], 61, "pct")]),
      sentence("Their box entries went from 2 to 7, and Okafor scored three minutes later.",
        [goal(41 * 60 + 18)], [claim("box_entries", "home", [38, 48], 7)]),
    ]),
  },
  {
    pendingAt: 63 * 60 + 30, confirmedAt: 64 * 60 + 50,
    pivot: pivot("pv-63", 63, "away", 3, [sub], "Substitution flipped the left flank", [
      sentence("After the change, Harbour City's final-third passes fell from 9 to 3.",
        inWindow(63, 73, (e) => e.team === "home" && e.type === "pass" && e.third === "final", 2),
        [claim("passes_final_third", "home", [63, 73], 3)]),
      sentence("Northvale won 6 of 8 duels on their right flank, where Moreau had been the outlet.",
        inWindow(63, 73, (e) => e.team === "away" && e.type === "duel", 1), [claim("duels_won", "away", [63, 73], 6)]),
      sentence("Northvale's pressures rose from 6 to 12, and their equaliser followed.",
        [goal(70 * 60 + 6)], [claim("pressures", "away", [63, 73], 12)]),
    ]),
  },
  {
    pendingAt: 73 * 60 + 55, confirmedAt: 74 * 60 + 40,
    pivot: pivot("pv-74", 74, "home", 2, [shift], "Back three steadied Harbour City", [
      sentence("Harbour City dropped into a back three, and Northvale's pressures fell from 12 to 5.",
        [shift, ...inWindow(74, 84, (e) => e.team === "away" && e.type === "pressure", 1)],
        [claim("pressures", "away", [74, 84], 5)]),
      sentence("Passes out of defence now found a teammate 14 of 16 times, up from 6 of 11.",
        inWindow(74, 84, (e) => e.team === "home" && e.type === "pass" && e.third === "defensive", 2),
        [claim("pass_accuracy_pct", "home", [74, 84], 88, "pct")]),
    ]),
  },
];

// Before/after table for S2: ten minutes either side, matching the figures the sentences quote.
const row = (label: string, c: Claim, before: number): BeforeAfterRow => {
  const [a, b] = c.stat_ref.window;
  return { label, after: c, before: { ...c, value: before, stat_ref: { ...c.stat_ref, window: [2 * a - b, a] } } };
};
const momentumRow = (minute: number): BeforeAfterRow => ({
  label: "Momentum (avg)",
  before: momentumAvg(metrics, [minute - 10, minute]),
  after: momentumAvg(metrics, [minute, minute + 10]),
});
const claims = (id: string) => pivots.find((p) => p.pivot.pivot_id === id)!.pivot.narrative!.sentences.flatMap((s) => s.claims);
const [c38, c63, c74] = [claims("pv-38"), claims("pv-63"), claims("pv-74")];
const BEFORE_AFTER: Record<string, BeforeAfterRow[]> = {
  "pv-38": [row("HCY possession", c38[0], 48), row("HCY box entries", c38[1], 2), momentumRow(38)],
  "pv-63": [row("HCY final-third passes", c63[0], 9), row("NVR duels won", c63[1], 3),
    row("NVR pressures", c63[2], 6), momentumRow(63)],
  "pv-74": [row("NVR pressures", c74[0], 12), row("HCY pass accuracy from defence", c74[1], 55), momentumRow(74)],
};

export const DEMO_1021: MatchFixture = {
  matchId: MATCH_ID,
  teams: TEAMS,
  players: PLAYERS,
  events,
  metrics,
  pivots,
  details: buildPivotDetails({
    matchId: MATCH_ID, events, metrics, pivots: pivots.map((p) => p.pivot), beforeAfter: BEFORE_AFTER,
    onPitch: (team, t) => onPitch(team, t, true),
  }),
  startAt: 73 * 60 + 30,
  endAt: 90 * 60,
};
