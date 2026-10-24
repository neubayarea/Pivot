// The What-if API without a backend, for `?fixture=1` and the tests. The chips follow the worker's
// catalog (apps/worker/src/pivot_worker/scenarios.py, options_for); runs advance on the wall clock
// so the progress bar moves, and the numbers come from a small score-state table nudged by the
// change, counted over n_runs replays with Wilson 95% ranges, like pivot_core/sim/whatif.py.
import type { MatchEvent, Narrative, OutcomeDist, Scenario, ScenarioSpec, SimResult } from "@pivot/contracts";
import { translator, type Lang } from "../i18n";
import { ApiError } from "./live/api";
import { DEFAULT_RUNS, MOVE_RANGE, OUTCOMES, RUN_COUNTS, clockMinute, optionLabel, type Outcome, type ScenarioApi, type ScenarioOption } from "./scenarios";
import type { MatchView, Side } from "./view";

/** How long a mock run takes, by its size: long enough to watch the bar, short enough for a demo. */
const DURATION_MS: Record<number, number> = { 200: 2400, 500: 3600, 1000: 5200 };
const QUEUED_MS = 300;
const DEFAULT_MOVE_TO = 74;                   // elapsed minute, shown as 75′
const Z95 = 1.959964;

type Run = { scenario: Scenario; startedAt: number; key: string };
const runs = new Map<string, Run>();
let counter = 0;

/** Forget every mock run (tests). */
export const resetMockScenarios = () => {
  runs.clear();
  counter = 0;
};

const isRed = (e: MatchEvent) => e.type === "card" && ["red", "second_yellow"].includes(String(e.meta.card ?? e.meta.colour ?? e.meta.color));
const isGoal = (e: MatchEvent) => e.type === "shot" && e.shot_outcome === "goal" && e.period !== 5;
const other = (s: Side): Side => (s === "home" ? "away" : "home");

/** options_for in the worker: one chip per catalog entry, the pivot's own trigger first, unavailable ones last. */
export function mockOptions(view: MatchView, pivotId: string): ScenarioOption[] {
  const pivot = view.pivotDetail(pivotId)?.pivot;
  if (!pivot) throw new ApiError(404, `GET /api/pivots/${pivotId}/scenarios: 404`);
  const played = view.events;
  const closest = (pool: MatchEvent[]) => {
    const triggers = pool.filter((e) => pivot.trigger_event_ids.includes(e.event_id));
    return (triggers.length ? triggers : [...pool].sort((a, b) => Math.abs(a.minute - pivot.minute) - Math.abs(b.minute - pivot.minute)))[0];
  };
  const target = (type: ScenarioOption["type"], pool: MatchEvent[], label: (m: number) => string, none: string): ScenarioOption => {
    const e = closest(pool);
    if (!e) return { type, label: label(-1), enabled: false, disabled_reason: none, target_event_id: null, at_minute: null, team: null, params: {} };
    if (type === "move_substitution") {
      const to = e.minute !== DEFAULT_MOVE_TO ? DEFAULT_MOVE_TO : DEFAULT_MOVE_TO - 10;
      return { type, label: `Move substitution to ${clockMinute(to)}′`, enabled: true, disabled_reason: null,
        target_event_id: e.event_id, at_minute: Math.min(e.minute, to), team: e.team, params: { new_minute: to } };
    }
    return { type, label: label(e.minute), enabled: true, disabled_reason: null, target_event_id: e.event_id, at_minute: e.minute, team: e.team, params: {} };
  };
  const subs = played.filter((e) => e.type === "substitution");
  const any = (m: number, what: string, verb: string) => (m < 0 ? `${verb} ${what}` : `${verb} ${clockMinute(m)}′ ${what}`);
  const losing = other(pivot.direction);
  const options = [
    target("cancel_substitution", subs, (m) => any(m, "substitution", "Cancel"), "No substitution in this match yet"),
    target("remove_red_card", played.filter(isRed), (m) => any(m, "red card", "Remove"), "No red card in this match"),
    target("move_substitution", subs, () => "Move substitution", "No substitution in this match yet"),
    target("remove_goal", played.filter(isGoal), (m) => any(m, "goal", "Disallow"), "No goal in this match yet"),
    { type: "change_press", label: `Press higher from ${clockMinute(pivot.minute)}′`, enabled: true, disabled_reason: null,
      target_event_id: null, at_minute: pivot.minute, team: losing, params: {} } satisfies ScenarioOption,
  ];
  return options.sort((a, b) => Number(!a.enabled) - Number(!b.enabled)
    || Number(!pivot.trigger_event_ids.includes(a.target_event_id ?? "")) - Number(!pivot.trigger_event_ids.includes(b.target_event_id ?? "")));
}

/** Small deterministic hash, so the same question gets the same numbers every time. */
function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return (h >>> 0) / 2 ** 32;
}

/** Final-result shares from the goal difference with this many minutes left. */
function fromState(diff: number, left: number): Record<Outcome, number> {
  const lead = Math.max(-2, Math.min(2, diff));
  const base = { [-2]: [0.04, 0.1, 0.86], [-1]: [0.13, 0.25, 0.62], 0: [0.37, 0.36, 0.27], 1: [0.66, 0.22, 0.12], 2: [0.88, 0.08, 0.04] }[lead]!;
  // Early on there is time to come back: pull towards the level-score shares.
  const w = Math.min(1, left / 90) * 0.5;
  const level = [0.37, 0.36, 0.27];
  const [h, d, a] = base.map((p, i) => p * (1 - w) + level[i] * w);
  return { home_win: h, draw: d, away_win: a };
}

/** Moves `points` of probability towards `side` winning, taken mostly from the other side's wins. */
function tilt(p: Record<Outcome, number>, side: Side, points: number): Record<Outcome, number> {
  const win: Outcome = side === "home" ? "home_win" : "away_win";
  const lose: Outcome = side === "home" ? "away_win" : "home_win";
  const out = { ...p };
  out[win] += points;
  out[lose] -= points * 0.65;
  out.draw -= points * 0.35;
  for (const k of OUTCOMES) out[k] = Math.min(0.97, Math.max(0.02, out[k]));
  const sum = OUTCOMES.reduce((s, k) => s + out[k], 0);
  for (const k of OUTCOMES) out[k] /= sum;
  return out;
}

export function wilson(k: number, n: number, z = Z95): [number, number] {
  if (n === 0) return [0, 1];
  const p = k / n;
  const den = 1 + (z * z) / n;
  const centre = (p + (z * z) / (2 * n)) / den;
  const half = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / den;
  return [Math.max(0, centre - half), Math.min(1, centre + half)];
}

/** Whole runs per outcome that add up to n, then the shares and their Wilson ranges. */
function count(p: Record<Outcome, number>, n: number): OutcomeDist {
  const k = OUTCOMES.map((o) => Math.floor(p[o] * n));
  k[1] += n - k[0] - k[1] - k[2];
  const dist = { home_advance: null, ci95: {} } as unknown as OutcomeDist;
  OUTCOMES.forEach((o, i) => {
    dist[o] = k[i] / n;
    dist.ci95[o] = wilson(k[i], n);
  });
  return dist;
}

const overlap = (a: [number, number], b: [number, number]) => a[0] <= b[1] && b[0] <= a[1];

/** How far the change moves the team it is about, in probability. */
function effect(spec: ScenarioSpec, view: MatchView, jitter: number): { side: Side; points: number } {
  const team = spec.team ?? "home";
  const pivot = view.pivotDetail(spec.pivot_id)?.pivot;
  const hurt = pivot ? pivot.direction !== team : true;   // the pivot swung against the team that made the change
  switch (spec.type) {
    case "cancel_substitution": return { side: team, points: (hurt ? 0.12 : -0.08) + jitter };
    case "move_substitution": {
      const earlier = Number(spec.params.new_minute ?? DEFAULT_MOVE_TO) < spec.at_minute + 1;
      return { side: team, points: (hurt ? (earlier ? -0.03 : 0.05) : earlier ? 0.04 : -0.03) + jitter / 2 };
    }
    case "remove_red_card": return { side: team, points: 0.13 + jitter };
    case "change_press": return { side: team, points: 0.05 + jitter / 2 };
    default: return { side: team, points: jitter };
  }
}

function simulate(spec: ScenarioSpec, view: MatchView): Pick<SimResult, "baseline" | "counterfactual" | "significant"> {
  const at = spec.at_minute;
  const goals = view.events.filter((e) => isGoal(e) && e.minute <= at && e.event_id !== spec.target_event_id);
  const scored = (side: Side) => goals.filter((e) => e.team === side).length;
  const target = spec.target_event_id ? view.eventById(spec.target_event_id) : undefined;
  // The baseline counts the target goal too; the change takes it away.
  const own = spec.type === "remove_goal" && target && target.minute <= at ? (target.team === "home" ? 1 : -1) : 0;
  const diff = scored("home") - scored("away");
  const left = 90 - at;
  const jitter = (hash(`${spec.pivot_id}|${spec.type}|${JSON.stringify(spec.params)}`) - 0.5) * 0.04;
  const base = fromState(diff + own, left);
  const changed = spec.type === "remove_goal" ? fromState(diff, left) : (() => {
    const { side, points } = effect(spec, view, jitter);
    return tilt(base, side, points);
  })();
  const baseline = count(base, spec.n_runs);
  const counterfactual = count(changed, spec.n_runs);
  const significant = Object.fromEntries(OUTCOMES.map((o) => [o, !overlap(baseline.ci95[o], counterfactual.ci95[o])]));
  return { baseline, counterfactual, significant };
}

/** The Comparator's explanation, in the viewer's language; words like "clear" only when the ranges part. */
function narrate(spec: ScenarioSpec, r: Pick<SimResult, "baseline" | "counterfactual" | "significant">, view: MatchView, option: ScenarioOption, lang: Lang): Narrative {
  const t = translator(lang);
  const side = spec.team ?? "home";
  const win: Outcome = side === "home" ? "home_win" : "away_win";
  const team = view.teams[side].name;
  const [before, after] = [Math.round(100 * r.baseline[win]), Math.round(100 * r.counterfactual[win])];
  const change = optionLabel(option, t, typeof spec.params.new_minute === "number" ? clockMinute(spec.params.new_minute) : undefined);
  const clear = r.significant[win];
  const evidence = [spec.target_event_id ?? view.pivotDetail(spec.pivot_id)?.pivot.trigger_event_ids[0] ?? spec.pivot_id] as [string];
  const sentence = (text: string) => ({ text, claims: [], context_ids: [], evidence_ids: evidence });
  return {
    chain_id: null,
    headline: t(after >= before ? "whatif.mock.headlineUp" : "whatif.mock.headlineDown", { team, points: Math.abs(after - before) }),
    prefs: { language: lang, audience: "analyst", focus_team: null, focus_player_id: null },
    source: "template",
    verifier_attempts: 1,
    sentences: [
      sentence(t("whatif.mock.compare", { change, team, after, before })),
      sentence(t(clear ? "whatif.mock.clear" : "whatif.mock.unclear", { n: spec.n_runs.toLocaleString(lang) })),
    ],
  };
}

/**
 * The mock API over the fixture's match, read through `read` so a replay ticking on does not make a
 * new one; runs are kept across pages, keyed like the API's cache.
 */
export function mockScenarioApi(read: () => { view: MatchView; lang: Lang }, now: () => number = Date.now): ScenarioApi {
  const get = async (scenarioId: string): Promise<Scenario> => {
    const { view, lang } = read();
    const run = runs.get(scenarioId);
    if (!run) throw new ApiError(404, `GET /api/scenarios/${scenarioId}: 404`);
    const { scenario: s } = run;
    if (s.status === "completed") return s;
    const elapsed = now() - run.startedAt;
    const total = 2 * s.spec.n_runs;
    if (elapsed < QUEUED_MS) return s;
    const duration = DURATION_MS[s.spec.n_runs] ?? DURATION_MS[DEFAULT_RUNS];
    if (elapsed < duration) return { ...s, status: "running", done: Math.floor((total * (elapsed - QUEUED_MS)) / (duration - QUEUED_MS)) };
    const option = mockOptions(view, s.spec.pivot_id).find((o) => o.type === s.spec.type)!;
    const numbers = simulate(s.spec, view);
    run.scenario = {
      ...s, status: "completed", done: total,
      result: { scenario_id: s.scenario_id, ...numbers, narrative: narrate(s.spec, numbers, view, option, lang), runtime_ms: duration, executor: "local_pool" },
    };
    return run.scenario;
  };

  return {
    options: async (pivotId) => mockOptions(read().view, pivotId),
    start: async (body) => {
      const { view } = read();
      const option = mockOptions(view, body.pivot_id).find((o) => o.type === body.type);
      const n = body.n_runs ?? DEFAULT_RUNS;
      if (!option?.enabled || !RUN_COUNTS.includes(n)) throw new ApiError(422, "POST /api/scenarios: 422");
      const params = { ...option.params, ...body.params };
      if (body.type === "move_substitution") {
        const to = Number(params.new_minute);
        if (!(clockMinute(to) >= MOVE_RANGE[0] && clockMinute(to) <= MOVE_RANGE[1])) throw new ApiError(422, "POST /api/scenarios: 422");
      }
      const target = option.target_event_id ? view.eventById(option.target_event_id) : undefined;
      const atMinute = body.type === "move_substitution" && target ? Math.min(target.minute, Number(params.new_minute)) : option.at_minute!;
      const key = JSON.stringify([body.pivot_id, body.type, n, params]);
      // Like the API's store: the same question again is answered at once.
      for (const run of runs.values()) if (run.key === key && run.scenario.status === "completed") return run.scenario;
      const id = `${view.match.match_id}:s${++counter}`;
      const scenario: Scenario = {
        scenario_id: id, match_id: view.match.match_id, status: "queued", done: 0, result: null,
        spec: { type: body.type, pivot_id: body.pivot_id, target_event_id: option.target_event_id, at_minute: atMinute,
          team: option.team, tactics: null, team_sheet: null, params, n_runs: n, seed_base: 1021000 },
      };
      runs.set(id, { scenario, startedAt: now(), key });
      return scenario;
    },
    get,
  };
}
