import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Button from "../components/Button";
import Card from "../components/Card";
import Kicker from "../components/Kicker";
import { pivotHeadline } from "../components/PivotList";
import Segmented from "../components/Segmented";
import Stamp from "../components/Stamp";
import { RunFailed, RunProgress, ScenarioChips, ScenarioResult, meaningOf } from "../components/WhatIf";
import { useClock } from "../data/clock";
import { useFixture, useMatch } from "../data/match";
import { mockScenarioApi } from "../data/scenarioMock";
import { numberLocale } from "../data/motion";
import { forYourTeam, usePersona } from "../data/persona";
import {
  DEFAULT_RUNS, MOVE_RANGE, RUN_COUNTS, clockMinute, liveScenarioApi, optionLabel, useOptionMinute, useScenarioRun, type RunCount,
  type ScenarioApi, type ScenarioOption, type StartScenario,
} from "../data/scenarios";
import { usePrefs } from "../i18n";
import NotFound from "./NotFound";

type Options = { kind: "loading" } | { kind: "error"; error: unknown } | { kind: "ready"; options: ScenarioOption[] };

const defaultMoveTo = (options: ScenarioOption[]) => {
  const m = options.find((o) => o.type === "move_substitution")?.params.new_minute;
  return typeof m === "number" ? clockMinute(m) : 75;
};

// S3 · What-if lab. Layout follows "07 S3" in docs/design/matchday-programme.html. Runs go to the
// API (A09), or to the mock when the page runs on the fixture (`?fixture=1`).
export default function WhatIfLab() {
  const { id = "" } = useParams();
  const source = useScenarioSource();
  return <Lab key={id} pivotId={id} source={source} />;
}

/** Where runs go: the API, or the mock on the fixture. Also used by the board's inline what-if. */
export function useScenarioSource(): ScenarioApi {
  const view = useMatch();
  const { prefs } = usePrefs();
  const fixture = useFixture();
  // The mock reads the match and language as they are when asked, so the replay ticking on keeps the same one.
  const read = useRef({ view, lang: prefs.language });
  read.current = { view, lang: prefs.language };
  return useMemo(() => (fixture ? mockScenarioApi(() => read.current) : liveScenarioApi), [fixture]);
}

export function Lab({ pivotId, source }: { pivotId: string; source: ScenarioApi }) {
  const { pivotDetail, teams, eventById } = useMatch();
  const { t } = usePrefs();
  const { minute } = useClock();
  const minuteOf = useOptionMinute();
  const { side, fan } = usePersona();
  const pivot = pivotDetail(pivotId)?.pivot;
  const [opts, setOpts] = useState<Options>({ kind: "loading" });
  const [reload, setReload] = useState(0);
  const [selected, setSelected] = useState<ScenarioOption["type"] | null>(null);
  const [runs, setRuns] = useState<RunCount>(DEFAULT_RUNS);
  const [moveTo, setMoveTo] = useState(75);
  const { state, run, reset } = useScenarioRun(source);
  const chipsRef = useRef<HTMLDivElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    setOpts({ kind: "loading" });
    source.options(pivotId).then(
      (options) => {
        if (!alive) return;
        setOpts({ kind: "ready", options });
        // The pivot's own trigger comes first: have it ready to run.
        setSelected((s) => s ?? forYourTeam(options, side).find((o) => o.enabled)?.type ?? null);
        setMoveTo(defaultMoveTo(options));
      },
      (error) => alive && setOpts({ kind: "error", error }),
    );
    return () => {
      alive = false;
    };
  }, [source, pivotId, reload]);

  // Keyboard and screen-reader users land on the result when it arrives.
  useEffect(() => {
    if (state.phase === "done") resultRef.current?.focus();
  }, [state.phase]);

  if (!pivot) {
    return (
      <NotFound title={t("detail.notFound.title")}>
        <p>{t("detail.notFound.body", { id: pivotId })}</p>
      </NotFound>
    );
  }

  // C12: with a ♥ team, what would have helped it comes first.
  const options = forYourTeam(opts.kind === "ready" ? opts.options : [], side);
  const option = options.find((o) => o.type === selected && o.enabled);
  const busy = state.phase === "starting" || state.phase === "running";
  const ranOption = "body" in state ? options.find((o) => o.type === state.body.type) : undefined;

  // Any change to the form clears the last answer: it was for something else.
  const edit = <A extends unknown[]>(fn: (...a: A) => void) => (...a: A) => {
    if (state.phase !== "idle") reset();
    fn(...a);
  };

  const body = (o: ScenarioOption): StartScenario => {
    const params = o.type === "move_substitution" ? { ...o.params, new_minute: moveTo - 1 } : o.params;
    return { pivot_id: pivotId, type: o.type, n_runs: runs, ...(Object.keys(params).length ? { params } : {}) };
  };

  const tryAnother = () => {
    reset();
    setSelected(null);
    setRuns(DEFAULT_RUNS);
    setMoveTo(defaultMoveTo(options));
    chipsRef.current?.querySelector<HTMLButtonElement>("button:not([aria-disabled])")?.focus();
  };

  // The replay starts at the earlier of the substitution and its new minute.
  const fromMinute = (o: ScenarioOption) => {
    const target = o.target_event_id ? eventById(o.target_event_id) : undefined;
    if (o.type === "move_substitution" && target) return minute(Math.min(target.minute, moveTo - 1));
    return o.at_minute === null ? null : minute(o.at_minute);
  };

  return (
    <>
      <div className="back">
        <Link to={`/pivot/${pivotId}`}>{t("whatif.back", { minute: minute(pivot.minute), headline: pivotHeadline(pivot, teams, t) })}</Link>
      </div>
      <div className="headline">
        <Kicker>{t("whatif.kicker")}</Kicker>
        <h1 className="x">{t("whatif.question")}</h1>
        <span className="sp" />
        <Stamp tone="warn">{t("whatif.simulated")}</Stamp>
      </div>
      {fan ? (
        // Ax91: a fan picks from big cards, each with what it means; one tap plays it out.
        <div className="wi-fan-lab">
          <section className="card wi-fan-pick" aria-labelledby="wi-fan-pick-hd">
            <h2 id="wi-fan-pick-hd">{t("wi.fan.pickTitle")}</h2>
            <p className="muted">{t("wi.fan.pickNote")}</p>
            {opts.kind === "loading" && (
              <div aria-busy="true" className="sk-lines">
                <p className="sr-only" role="status">{t("whatif.loadingOptions")}</p>
                {[0, 1, 2].map((i) => <span key={i} className="sk sk-line" aria-hidden="true" />)}
              </div>
            )}
            {opts.kind === "error" && (
              <div role="alert" className="run-failed">
                <p>{t("whatif.optionsError")}</p>
                <div className="comp-row"><Button onClick={() => setReload((n) => n + 1)}>{t("whatif.retry")}</Button></div>
              </div>
            )}
            {opts.kind === "ready" && (options.some((o) => o.enabled) ? (
              <div ref={chipsRef} className="wi-fan-cards" role="group" aria-label={t("whatif.pickLabel")}>
                {options.filter((o) => o.enabled).map((o) => (
                  <button key={o.type} type="button" className="wi-fan-card" aria-pressed={ranOption?.type === o.type}
                    disabled={busy} onClick={() => { setSelected(o.type); run(body(o)); }}>
                    <b>{optionLabel(o, t, o.type === "move_substitution" ? moveTo : undefined, minuteOf(o))}</b>
                    <span>{meaningOf(o, t, minuteOf(o))}</span>
                    {o.team && <small>{teams[o.team].name}</small>}
                  </button>
                ))}
              </div>
            ) : (
              <p className="muted">{t("whatif.noOptions")}</p>
            ))}
          </section>
          <div ref={resultRef} tabIndex={-1} className="result-slot card">
            {state.phase === "idle" && <div className="placeholder">{t("wi.fan.idle")}</div>}
            {(state.phase === "starting" || state.phase === "running") && <RunProgress scenario={state.phase === "running" ? state.scenario : null} />}
            {state.phase === "failed" && (
              <RunFailed error={state.error} onRetry={() => run(state.body, { fresh: true })} onReset={tryAnother} />
            )}
            {state.phase === "done" && <ScenarioResult state={state} option={ranOption} teams={teams} onReset={tryAnother} source={source} />}
          </div>
        </div>
      ) : (
      <div className="grid3">
        <div className="stack">
          <Card title={t("whatif.pickTitle")} note={opts.kind === "ready" ? t("whatif.pickNote", { n: options.filter((o) => o.enabled).length }) : undefined}>
            {opts.kind === "loading" && (
              <div aria-busy="true" className="sk-lines">
                <p className="sr-only" role="status">{t("whatif.loadingOptions")}</p>
                {[0, 1, 2, 3].map((i) => <span key={i} className="sk sk-line" aria-hidden="true" />)}
              </div>
            )}
            {opts.kind === "error" && (
              <div role="alert" className="run-failed">
                <p>{t("whatif.optionsError")}</p>
                <div className="comp-row">
                  <Button onClick={() => setReload((n) => n + 1)}>{t("whatif.retry")}</Button>
                </div>
              </div>
            )}
            {opts.kind === "ready" && (options.length ? (
              <div ref={chipsRef}>
                <ScenarioChips options={options} selected={selected} onSelect={edit(setSelected)} teams={teams} moveTo={moveTo} />
              </div>
            ) : (
              <p className="muted">{t("whatif.noOptions")}</p>
            ))}
          </Card>
          <Card title={t("whatif.confirmTitle")}>
            {option ? (
              <>
                <dl className="conf">
                  <dt>{t("whatif.confirm.change")}</dt>
                  <dd>{optionLabel(option, t, moveTo, minuteOf(option))}</dd>
                  {option.team && (
                    <>
                      <dt>{t("whatif.confirm.team")}</dt>
                      <dd>{teams[option.team].name}</dd>
                    </>
                  )}
                  {fromMinute(option) !== null && (
                    <>
                      <dt>{t("whatif.confirm.from")}</dt>
                      <dd>{t("whatif.confirm.fromValue", { minute: fromMinute(option)! })}</dd>
                    </>
                  )}
                  <dt>{t("whatif.confirm.runs")}</dt>
                  <dd>
                    <Segmented
                      label={t("whatif.runsLabel")}
                      options={RUN_COUNTS.map((n) => ({ value: String(n), label: n.toLocaleString(numberLocale()) }))}
                      value={String(runs)}
                      onChange={edit((v: string) => setRuns(Number(v) as RunCount))}
                    />
                  </dd>
                </dl>
                {option.type === "move_substitution" && (
                  <div className="move-to">
                    <label htmlFor="whatif-move">{t("whatif.moveTo")}</label>
                    <input
                      id="whatif-move"
                      type="range"
                      min={MOVE_RANGE[0]}
                      max={MOVE_RANGE[1]}
                      value={moveTo}
                      aria-valuetext={`${moveTo}′`}
                      onChange={edit((e: React.ChangeEvent<HTMLInputElement>) => setMoveTo(Number(e.target.value)))}
                    />
                    <output htmlFor="whatif-move" className="num">{moveTo}′</output>
                    <small className="muted">{t("whatif.moveHint", { min: MOVE_RANGE[0], max: MOVE_RANGE[1] })}</small>
                  </div>
                )}
                <p className="fine">{t("whatif.runsNote")}</p>
                <div className="comp-row">
                  <Button variant="primary" disabled={busy} onClick={() => run(body(option))}>
                    {t(busy ? "whatif.running" : "whatif.run")}
                  </Button>
                </div>
              </>
            ) : (
              <p className="muted">{t("whatif.pickFirst")}</p>
            )}
          </Card>
        </div>
        <Card
          title={t("whatif.resultTitle")}
          note={state.phase === "done"
            ? t("whatif.resultNote", { n: state.scenario.spec.n_runs.toLocaleString(numberLocale()), s: (state.scenario.result.runtime_ms / 1000).toFixed(1) })
            : undefined}
        >
          <div ref={resultRef} tabIndex={-1} className="result-slot">
            {state.phase === "idle" && <div className="placeholder">{t("whatif.idle")}</div>}
            {(state.phase === "starting" || state.phase === "running") && <RunProgress scenario={state.phase === "running" ? state.scenario : null} />}
            {state.phase === "failed" && (
              <RunFailed error={state.error} onRetry={() => run(state.body, { fresh: true })} onReset={tryAnother} />
            )}
            {state.phase === "done" && <ScenarioResult state={state} option={ranOption} teams={teams} onReset={tryAnother} source={source} />}
          </div>
          <p className="fine">{t("whatif.fine")}</p>
        </Card>
      </div>
      )}
    </>
  );
}
