// Ax91 (#431): a fan's What-if tab is one ranked list, "the biggest what-ifs of this match", across
// every turning point. Each row asks a question in plain words; a stored answer gives it an impact
// from the viewer's side and puts it near the top. Tapping a row opens its answer in place, one at a
// time, and the top one is open on arrival. Changes with no stored answer follow as "Try it": a tap
// plays them 200 times with the usual progress.
import { useEffect, useMemo, useState } from "react";
import type { Pivot1 as Pivot, Scenario, SimResult } from "@pivot/contracts";
import Stamp from "../../components/Stamp";
import { RunFailed, RunProgress, ScenarioResult } from "../../components/WhatIf";
import { useClock } from "../../data/clock";
import { useMatch } from "../../data/match";
import { forYourTeam, usePersona } from "../../data/persona";
import {
  DEFAULT_RUNS, biggestShift, cacheKey, clockMinute, knownScenario, optionLabel, pct, rememberScenario, useOptionMinute,
  useScenarioRun, type Outcome, type ScenarioApi, type ScenarioOption, type StartScenario,
} from "../../data/scenarios";
import { useT, type T } from "../../i18n";

type Answered = Scenario & { result: SimResult };
type Item = { key: string; pivot: Pivot; n: number; option: ScenarioOption; body: StartScenario; answer: Answered | null };

/** The most striking change first, for the ones not played yet. */
const STRIKING: ScenarioOption["type"][] = ["remove_goal", "remove_red_card", "cancel_substitution", "move_substitution", "change_press"];
const rank = (o: ScenarioOption) => (STRIKING.indexOf(o.type) + STRIKING.length + 1) % (STRIKING.length + 1);

// Options and stored answers are read once per pivot for the session, not on every render.
const optionsRead = new WeakMap<ScenarioApi, Map<string, Promise<ScenarioOption[]>>>();
const readOptions = (source: ScenarioApi, pivotId: string) => {
  const m = optionsRead.get(source) ?? new Map<string, Promise<ScenarioOption[]>>();
  optionsRead.set(source, m);
  if (!m.has(pivotId)) {
    const p = source.options(pivotId);
    p.catch(() => m.delete(pivotId));
    m.set(pivotId, p);
  }
  return m.get(pivotId)!;
};
const answersRead = new Map<string, Promise<Answered | null>>();
/** A stored answer: asking for it answers at once (the API's store), so this never starts a slow run. */
const readAnswer = (source: ScenarioApi, body: StartScenario): Promise<Answered | null> => {
  const known = knownScenario(body);
  if (known) return Promise.resolve(known);
  const k = cacheKey(body);
  if (!answersRead.has(k)) {
    answersRead.set(k, source.start(body).then((s) => {
      if (s.status !== "completed" || !s.result) return null;
      rememberScenario(body, s);
      return s as Answered;
    }, () => null));
  }
  return answersRead.get(k)!;
};

const bodyOf = (pivotId: string, o: ScenarioOption): StartScenario =>
  ({ pivot_id: pivotId, type: o.type, n_runs: DEFAULT_RUNS, ...(Object.keys(o.params).length ? { params: o.params } : {}) });

/** The outcome a row's impact follows: the ♥ team winning, else whichever moved most. */
const focusOf = (r: SimResult, side: "home" | "away" | null): Outcome => (side ? `${side}_win` : biggestShift(r).outcome);
const impactOf = (r: SimResult, side: "home" | "away" | null) => {
  const k = focusOf(r, side);
  return { outcome: k, was: pct(r.baseline[k]), now: pct(r.counterfactual[k]) };
};

export function FanWhatIfs({ moments, source }: { moments: Pivot[]; source: ScenarioApi }) {
  const t = useT();
  const { minute } = useClock();
  const { side } = usePersona();
  const [items, setItems] = useState<Item[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [moment, setMoment] = useState<string | null>(null);
  const ids = moments.map((p) => p.pivot_id).join(",");

  useEffect(() => {
    let alive = true;
    setItems(null);
    setFailed(false);
    Promise.all(moments.map(async (pivot, i) => {
      const opts = forYourTeam(await readOptions(source, pivot.pivot_id), side).filter((o) => o.enabled);
      return Promise.all(opts.map(async (option): Promise<Item> => {
        const body = bodyOf(pivot.pivot_id, option);
        const answer = option.stored || knownScenario(body) ? await readAnswer(source, body) : null;
        return { key: `${pivot.pivot_id}|${option.type}`, pivot, n: i + 1, option, body, answer };
      }));
    })).then((all) => {
      if (!alive) return;
      const flat = all.flat();
      setItems(flat);
      setOpen((o) => o ?? sorted(flat, side)[0]?.key ?? null);
    }, () => alive && setFailed(true));
    return () => {
      alive = false;
    };
    // `moments` is read through `ids`; a new array with the same pivots is the same list.
  }, [source, ids, side]);

  const list = useMemo(() => (items ? sorted(items, side) : []), [items, side]);
  // The same change asked from two turning points is one question: the row that moved it most stays.
  const seen = new Set<string>();
  const shown = list.filter((it) => {
    if (moment !== null && it.pivot.pivot_id !== moment) return false;
    const same = JSON.stringify([it.option.type, it.option.target_event_id, it.option.params]);
    if (seen.has(same)) return false;
    seen.add(same);
    return true;
  });
  const answered = shown.filter((it) => it.answer);
  const toTry = shown.filter((it) => !it.answer);

  return (
    <section className="wi-list" aria-labelledby="wi-list-hd">
      <header className="wi-list-head">
        <h2 id="wi-list-hd">{t("wi.list.title")}</h2>
        <Stamp tone="warn">{t("whatif.simulated")}</Stamp>
        <p className="muted">{t("wi.list.note")}</p>
      </header>
      {moments.length > 1 && (
        <div className="chips wi-list-moments" role="group" aria-label={t("wi.list.moments")}>
          <button type="button" className="chip" aria-pressed={moment === null} onClick={() => setMoment(null)}>{t("wi.list.all")}</button>
          {moments.map((p, i) => (
            <button key={p.pivot_id} type="button" className="chip" aria-pressed={moment === p.pivot_id} onClick={() => setMoment(p.pivot_id)}
              aria-label={t("post.whatIfAt", { n: i + 1, minute: minute(p.minute) })}>
              <span className="badge" aria-hidden="true">{i + 1}</span>
              <b className="num">{minute(p.minute)}′</b>
            </button>
          ))}
        </div>
      )}
      {failed ? (
        <p role="alert" className="run-failed">{t("whatif.optionsError")}</p>
      ) : items === null ? (
        <div aria-busy="true" className="sk-lines">
          <p className="sr-only" role="status">{t("whatif.loadingOptions")}</p>
          {[0, 1, 2].map((i) => <span key={i} className="sk sk-line" aria-hidden="true" />)}
        </div>
      ) : shown.length === 0 ? (
        <p className="muted">{t("whatif.noOptions")}</p>
      ) : (
        <>
          {answered.length > 0 && (
            <ol className="wi-rows">
              {answered.map((it) => (
                <Row key={it.key} item={it} open={open === it.key} onToggle={() => setOpen(open === it.key ? null : it.key)} source={source} />
              ))}
            </ol>
          )}
          {toTry.length > 0 && (
            <>
              <h3 className="wi-list-sub">{t(answered.length ? "wi.list.more" : "wi.list.title")}</h3>
              <p className="muted wi-list-subnote">{t("wi.list.moreNote")}</p>
              <ul className="wi-rows">
                {toTry.map((it) => (
                  <Row key={it.key} item={it} open={open === it.key} onToggle={() => setOpen(open === it.key ? null : it.key)} source={source} />
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  );
}

/** Played ones first, the biggest move for the viewer's side on top; the rest most striking first. */
function sorted(items: Item[], side: "home" | "away" | null): Item[] {
  const size = (it: Item) => {
    if (!it.answer) return -1;
    const { was, now } = impactOf(it.answer.result, side);
    return Math.abs(now - was);
  };
  return [...items].sort((a, b) => size(b) - size(a) || a.n - b.n || rank(a.option) - rank(b.option));
}

/** "What if Sadoseno's 17′ goal hadn't counted?": the question a row asks, from the option and its event. */
export function questionOf(o: ScenarioOption, t: T, at: string | null, who: string | null, team: string | null): string {
  const minute = at ?? "";
  switch (o.type) {
    case "remove_goal":
    case "remove_red_card":
      return who ? t(`wi.q.${o.type}`, { who, minute }) : t(`wi.q.${o.type}.any`, { minute });
    case "cancel_substitution":
      if (team) return t("wi.q.cancel_substitution", { team, minute });
      break;
    case "move_substitution":
      if (team && typeof o.params.new_minute === "number") return t("wi.q.move_substitution", { team, minute, to: clockMinute(o.params.new_minute) });
      break;
    case "change_press":
      if (team) return t(/lower/i.test(o.label) ? "wi.q.change_press.lower" : "wi.q.change_press.higher", { team, minute });
      break;
  }
  return t("wi.q.other", { change: optionLabel(o, t, undefined, at) });
}

function Row({ item, open, onToggle, source }: { item: Item; open: boolean; onToggle: () => void; source: ScenarioApi }) {
  const t = useT();
  const { teams, eventById, playerName } = useMatch();
  const { minute } = useClock();
  const { side } = usePersona();
  const minuteOf = useOptionMinute();
  const { option, answer, pivot } = item;
  const event = option.target_event_id ? eventById(option.target_event_id) : undefined;
  const who = event?.player_id ? playerName(event.player_id) || null : null;
  const teamSide = option.team ?? event?.team ?? null;
  const at = minuteOf(option);
  const question = questionOf(option, t, at, who, teamSide ? teams[teamSide].name : null);
  const panel = `wi-row-${item.key.replace(/[^a-zA-Z0-9-]/g, "-")}`;
  const impact = answer ? impactOf(answer.result, side) : null;
  const delta = impact ? impact.now - impact.was : 0;
  const whose = impact
    ? impact.outcome === "draw" ? t("wi.list.draw") : t("wi.list.win", { team: teams[impact.outcome === "home_win" ? "home" : "away"].name })
    : "";
  return (
    <li className={`wi-row${open ? " is-open" : ""}`}>
      <button type="button" className="wi-row-q" aria-expanded={open} aria-controls={panel} onClick={onToggle}>
        <span className="wi-row-text">
          <b>{question}</b>
          <span className="wi-row-meta">
            <span className="wi-row-moment"><span className="badge" aria-hidden="true">{item.n}</span>{t("wi.list.moment", { n: item.n, minute: minute(pivot.minute) })}</span>
          </span>
        </span>
        {impact ? (
          <span className={`wi-row-impact${delta > 0 ? " up" : delta < 0 ? " down" : ""}`}
            style={{ "--tc": impact.outcome === "draw" ? "var(--pv-ink-2)" : `var(--pv-${impact.outcome === "home_win" ? "home" : "away"})` } as React.CSSProperties}>
            <small>{whose}</small>
            <b className="num">{t("wi.list.wasNow", { was: impact.was, now: impact.now })}</b>
          </span>
        ) : (
          <span className="wi-row-try">{t("wi.list.try")}</span>
        )}
      </button>
      {open && (
        <div id={panel} className="wi-row-answer">
          <Answer item={item} source={source} onClose={onToggle} />
        </div>
      )}
    </li>
  );
}

/** One row's answer: at once when it is stored, else the run with its progress. */
function Answer({ item, source, onClose }: { item: Item; source: ScenarioApi; onClose: () => void }) {
  const { teams } = useMatch();
  const { state, run } = useScenarioRun(source);
  const key = cacheKey(item.body);
  useEffect(() => {
    run(item.body);
    // One run per question: the body is the same object for the same key.
  }, [key, run]);
  if (state.phase === "idle" || state.phase === "starting" || state.phase === "running") {
    return <RunProgress scenario={state.phase === "running" ? state.scenario : null} />;
  }
  if (state.phase === "failed") return <RunFailed error={state.error} onRetry={() => run(state.body, { fresh: true })} onReset={onClose} />;
  return <ScenarioResult state={state} option={item.option} teams={teams} onReset={onClose} source={source} />;
}
