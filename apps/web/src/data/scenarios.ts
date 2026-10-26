// What-if runs for S3 (C05). The page talks to a ScenarioApi: the REST API by default (A09), or
// the mock in data/scenarioMock with `?fixture=1`. runScenario starts a run, polls it about once a
// second (a pushed "scenario" envelope wakes it sooner) and resolves with the settled Scenario.
// Finished runs are kept for the session, so asking the same thing again answers at once.
import { useCallback, useContext, useEffect, useRef, useState } from "react";
import type { OutcomeDist, Scenario, SimResult } from "@pivot/contracts";
import type { T } from "../i18n";
import { eventMinute, useClock } from "./clock";
import { api, type RunCount, type ScenarioOption, type StartScenario } from "./live/api";
import { subscribeScenario } from "./live/scenarioFeed";
import { MatchContext } from "./view";

export type { RunCount, ScenarioOption, StartScenario };

export type ScenarioApi = {
  options: (pivotId: string) => Promise<ScenarioOption[]>;
  start: (body: StartScenario) => Promise<Scenario>;
  get: (scenarioId: string) => Promise<Scenario>;
};

export const liveScenarioApi: ScenarioApi = {
  options: api.listScenarioOptions,
  start: api.startScenario,
  get: api.getScenario,
};

export const RUN_COUNTS: readonly RunCount[] = [200, 500, 1000];
export const DEFAULT_RUNS: RunCount = 200;
export const POLL_MS = 1000;
/** Polls in a row that may fail (a blip in the connection) before the run counts as failed. */
const MAX_POLL_ERRORS = 5;
/** A moved substitution lands between these clock minutes (worker scenarios.py MOVE_MIN/MAX). */
export const MOVE_RANGE = [46, 85] as const;

export const OUTCOMES = ["home_win", "draw", "away_win"] as const;
export type Outcome = (typeof OUTCOMES)[number];

/** Each paired run plays the match twice: as it was, and with the change. */
export const totalRuns = (s: Pick<Scenario, "spec">) => 2 * s.spec.n_runs;
export const progressOf = (s: Scenario) => (s.status === "completed" ? 1 : Math.min(1, Math.max(0, s.done / totalRuns(s))));
const settled = (s: Scenario) => s.status === "completed" || s.status === "failed";

const cache = new Map<string, Scenario>();
export const cacheKey = (b: StartScenario) =>
  JSON.stringify([b.pivot_id, b.type, b.n_runs ?? DEFAULT_RUNS, Object.entries(b.params ?? {}).sort()]);
export const clearScenarioCache = () => cache.clear();

type RunOpts = {
  onUpdate: (s: Scenario) => void;
  signal: AbortSignal;
  pollMs?: number;
};

const aborted = () => new DOMException("The run was left", "AbortError");

/** Starts a run and follows it until it completes or fails; throws when it cannot be started or followed. */
export async function runScenario(source: ScenarioApi, body: StartScenario, { onUpdate, signal, pollMs = POLL_MS }: RunOpts): Promise<Scenario> {
  let s = await source.start(body);
  if (signal.aborted) throw aborted();
  onUpdate(s);
  let wake = () => {};
  // A push only moves the bar; a finished one wakes the poll so the result is read over REST.
  const unsubscribe = subscribeScenario((push) => {
    if (push.scenario_id !== s.scenario_id || settled(s)) return;
    if (typeof push.done === "number" && push.done > s.done) {
      s = { ...s, done: push.done, status: s.status === "queued" ? "running" : s.status };
      onUpdate(s);
    }
    if (push.status === "completed" || push.status === "failed") wake();
  });
  let errors = 0;
  try {
    while (!settled(s)) {
      await new Promise<void>((resolve) => {
        const timer = setTimeout(resolve, pollMs);
        wake = () => (clearTimeout(timer), resolve());
        signal.addEventListener("abort", wake, { once: true });
      });
      if (signal.aborted) throw aborted();
      try {
        s = await source.get(s.scenario_id);
        errors = 0;
      } catch (err) {
        if (++errors >= MAX_POLL_ERRORS) throw err;
        continue;
      }
      if (signal.aborted) throw aborted();
      onUpdate(s);
    }
  } finally {
    unsubscribe();
  }
  return s;
}

export type RunState =
  | { phase: "idle" }
  | { phase: "starting"; body: StartScenario }
  | { phase: "running"; body: StartScenario; scenario: Scenario }
  /** `cached`: answered at once, from this session or the API's own store. */
  | { phase: "done"; body: StartScenario; scenario: Scenario & { result: SimResult }; cached: boolean }
  | { phase: "failed"; body: StartScenario; scenario: Scenario | null; error: unknown };

/** The page's run: start one, retry it, or clear it ("Try another"). Leaving the page stops following it. */
export function useScenarioRun(source: ScenarioApi) {
  const [state, setState] = useState<RunState>({ phase: "idle" });
  const ctl = useRef<AbortController | null>(null);

  useEffect(() => () => ctl.current?.abort(), []);

  const run = useCallback((body: StartScenario, { fresh = false } = {}) => {
    ctl.current?.abort();
    const hit = fresh ? undefined : cache.get(cacheKey(body));
    if (hit?.result) {
      setState({ phase: "done", body, scenario: hit as Scenario & { result: SimResult }, cached: true });
      return;
    }
    const c = new AbortController();
    ctl.current = c;
    setState({ phase: "starting", body });
    let first = true;
    let instant = false;
    runScenario(source, body, {
      signal: c.signal,
      onUpdate: (scenario) => {
        if (first) instant = scenario.status === "completed";
        first = false;
        setState({ phase: "running", body, scenario });
      },
    }).then(
      (scenario) => {
        if (c.signal.aborted) return;
        if (scenario.status === "completed" && scenario.result) {
          cache.set(cacheKey(body), scenario);
          setState({ phase: "done", body, scenario: scenario as Scenario & { result: SimResult }, cached: instant });
        } else {
          setState({ phase: "failed", body, scenario, error: null });
        }
      },
      (error) => {
        if (!c.signal.aborted) setState((prev) => ({ phase: "failed", body, scenario: "scenario" in prev ? prev.scenario : null, error }));
      },
    );
  }, [source]);

  const reset = useCallback(() => {
    ctl.current?.abort();
    setState({ phase: "idle" });
  }, []);

  return { state, run, reset };
}

/**
 * A moved substitution's `new_minute` to the clock minute it is made at: the simulator plants it
 * when the clock shows new_minute + 1 (whatif._apply), so 74 → 75′. Other elapsed minutes go
 * through the match clock instead (data/clock.ts), since stoppage time shifts them.
 */
export const clockMinute = (elapsed: number) => elapsed + 1;

/**
 * The minute a chip names, as the rest of the page reads it (G2): the target event's own minute,
 * exactly as the event list shows it, else `at_minute` on the match clock (change_press: the pivot's).
 */
export function useOptionMinute(): (o: ScenarioOption) => string | null {
  const view = useContext(MatchContext);
  const { minute } = useClock();
  return (o) => {
    const target = o.target_event_id ? view?.eventById(o.target_event_id) : undefined;
    if (target?.clock_label) return eventMinute(target);
    return o.at_minute === null ? null : minute(o.at_minute);
  };
}

/**
 * The chip's label in the viewer's language. The API sends English with the minute filled in; the
 * minute comes from the option itself, so every language (and a picked new minute) reads the same.
 * `at` is the option's minute from useOptionMinute; without it, at_minute + 1.
 */
export function optionLabel(o: ScenarioOption, t: T, newMinute?: number, at?: string | null): string {
  const minute = at !== undefined ? at : o.at_minute === null ? null : String(clockMinute(o.at_minute));
  switch (o.type) {
    case "cancel_substitution":
    case "remove_red_card":
    case "remove_goal":
      return o.enabled && minute !== null ? t(`whatif.type.${o.type}`, { minute }) : t(`whatif.type.${o.type}.any`);
    case "move_substitution": {
      const to = newMinute ?? (typeof o.params.new_minute === "number" ? clockMinute(o.params.new_minute) : null);
      return to === null ? o.label : t("whatif.type.move_substitution", { minute: to });
    }
    case "change_press":
      return minute === null ? o.label : t(/lower/i.test(o.label) ? "whatif.type.change_press.lower" : "whatif.type.change_press.higher", { minute });
    default:
      return o.label;
  }
}

/** Why a chip is greyed out, in the viewer's language when it is one of the catalog's reasons. */
export function disabledReason(o: ScenarioOption, t: T): string {
  const known = {
    cancel_substitution: "whatif.none.substitution",
    move_substitution: "whatif.none.substitution",
    remove_red_card: "whatif.none.red",
    remove_goal: "whatif.none.goal",
  } as const;
  const key = known[o.type as keyof typeof known];
  // Only the catalog's own "nothing in the match fits" reason is translated; anything else is shown as sent.
  if (key && (!o.disabled_reason || /^No /.test(o.disabled_reason))) return t(key);
  return o.disabled_reason ?? t("whatif.unavailable");
}

/** The outcome that moved most, in percentage points, and whether its 95% ranges stopped overlapping. */
export function biggestShift(r: Pick<SimResult, "baseline" | "counterfactual" | "significant">) {
  const shifts = OUTCOMES.map((k) => ({ outcome: k, points: Math.round(100 * (r.counterfactual[k] - r.baseline[k])), significant: !!r.significant[k] }));
  // Prefer an outcome that clearly moved, then the largest move.
  return shifts.sort((a, b) => Number(b.significant) - Number(a.significant) || Math.abs(b.points) - Math.abs(a.points))[0];
}

export const pct = (p: number) => Math.round(100 * p);

/** The 95% range of one outcome, falling back to the point when the API left it out. */
export const ci = (d: OutcomeDist, k: Outcome): [number, number] => d.ci95[k] ?? [d[k], d[k]];
