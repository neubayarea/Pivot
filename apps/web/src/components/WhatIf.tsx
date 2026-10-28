// The pieces of S3 (What-if Lab), kept apart from the page so the tests can render each state.
// Layout follows "07 S3" in docs/design/matchday-programme.html.
import { useId, type CSSProperties } from "react";
import type { ArmStats, OutcomeDist, Scenario, ScoreShare, SimResult, Spread } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { ApiError } from "../data/live/api";
import type { MatchView } from "../data/match";
import { numberLocale } from "../data/motion";
import { usePersona } from "../data/persona";
import {
  OUTCOMES, biggestShift, ci, disabledReason, optionLabel, pct, progressOf, totalRuns, useComparisonIn, useOptionMinute,
  type Outcome, type RunState, type ScenarioApi, type ScenarioOption,
} from "../data/scenarios";
import { narrativeLang, usePrefs, useT, type MessageKey, type T } from "../i18n";
import Button from "./Button";
import LangTag from "./LangTag";
import Stamp from "./Stamp";
import "../styles/whatif.css";

type Teams = MatchView["teams"];
type Chosen = ScenarioOption["type"];

/** A share as a CSS length, rounded so the markup stays readable. */
const at = (p: number) => `${Math.round(10000 * p) / 100}%`;

const SEG_CLASS: Record<Outcome, string> = { home_win: "h", draw: "d", away_win: "a" };

/** "HCY", "Draw", "NVR": what each part of a bar is called. */
const outcomeShort = (k: Outcome, teams: Teams, t: T) =>
  k === "draw" ? t("whatif.draw") : teams[k === "home_win" ? "home" : "away"].short_name;

/** "3–1": a final score, home first. */
const scoreText = (s: ScoreShare) => `${s.home}–${s.away}`;

/** What the verdict sentence needs, all of it read off the result (no model writes these numbers). */
export type StoryInput = {
  result: Pick<SimResult, "baseline" | "counterfactual" | "significant" | "baseline_stats" | "counterfactual_stats">;
  /** The scenario type, the option's minute and its label, for the "If …" clause. */
  type: string;
  minute: string | null;
  change: string;
  pressLower?: boolean;
  teams: Teams;
  /** A fan's ♥ team (Ax91): the sentence follows its chance of winning instead of the outcome that moved most. */
  side?: "home" | "away" | null;
};

/** The "If …" clause: what was changed, in words. Types without one read "With the change (…)". */
function ifClause({ type, minute, change, pressLower }: StoryInput, t: T): string {
  const known = ["cancel_substitution", "remove_red_card", "remove_goal", "move_substitution"];
  if (minute !== null && known.includes(type)) return t(`whatif.if.${type}` as MessageKey, { minute });
  if (minute !== null && type === "change_press") return t(pressLower ? "whatif.if.change_press.lower" : "whatif.if.change_press.higher", { minute });
  return t("whatif.if.other", { change });
}

/**
 * The result as one sentence: "Without the 38′ red card, Harbour City's chance of winning falls
 * from 82% to 46%, and the most likely score goes from 3–1 to 1–1". The outcome is the one the big
 * number shows; the score clause needs both arms' stats (results stored before Bx10 have none).
 */
/** "1-2" becomes "1–2" and "38'" becomes "38′" in a sentence (C13 QA); a formation like 4-3-3 is left alone. */
export const scoreDashes = (text: string) =>
  text.replace(/(?<![\d-])(\d{1,2})-(\d{1,2})(?![\d-])/g, "$1–$2").replace(/(\d)'(?=[\s,.;:)]|$)/g, "$1′");

/** A team name ending in s takes a bare apostrophe: "Northgate Rovers’ chance", not "Rovers’s" or "Rovers's". */
const possessive = (text: string) => text.replace(/s['’]s\b/g, "s’");

export function storyLine(input: StoryInput, t: T): string {
  const { result: r, teams } = input;
  const outcome: Outcome = input.side ? `${input.side}_win` : biggestShift(r).outcome;
  const [before, after] = [pct(r.baseline[outcome]), pct(r.counterfactual[outcome])];
  const way = after > before ? "up" : after < before ? "down" : "same";
  const chance = outcome === "draw"
    ? t(`whatif.story.draw.${way}`, { before, after })
    : t(`whatif.story.win.${way}`, { team: teams[outcome === "home_win" ? "home" : "away"].name, before, after });
  const [was, now] = [r.baseline_stats?.top_scores[0], r.counterfactual_stats?.top_scores[0]];
  const vars = { if: ifClause(input, t), chance };
  if (!was || !now) return possessive(t("whatif.storyShort", vars));
  const score = scoreText(was) === scoreText(now)
    ? t("whatif.story.scoreSame", { before: scoreText(was) })
    : t("whatif.story.score", { before: scoreText(was), after: scoreText(now) });
  return possessive(t("whatif.story", { ...vars, score }));
}

type ChipsProps = {
  options: ScenarioOption[];
  selected: Chosen | null;
  onSelect: (type: Chosen) => void;
  teams: Teams;
  /** The clock minute picked for move_substitution, so its chip reads the same as the confirm card. */
  moveTo?: number;
};

/** One button per scenario this match can have; the others are named on one line, with why. */
export function ScenarioChips({ options, selected, onSelect, teams, moveTo }: ChipsProps) {
  const t = useT();
  const minuteOf = useOptionMinute();
  const id = useId();
  return (
    <div className="scn" role="group" aria-label={t("whatif.pickLabel")}>
      {/* C13 UX: the changes this match cannot have go on one quiet line under the rest. */}
      {options.filter((o) => o.enabled).map((o) => {
        const reason = o.enabled ? null : disabledReason(o, t);
        return (
          <button
            key={o.type}
            type="button"
            aria-pressed={o.enabled ? selected === o.type : undefined}
            aria-disabled={o.enabled ? undefined : true}
            aria-describedby={reason ? `${id}-${o.type}` : undefined}
            className={o.enabled ? undefined : "off"}
            onClick={() => o.enabled && onSelect(o.type)}
          >
            <span>{optionLabel(o, t, o.type === "move_substitution" ? moveTo : undefined, minuteOf(o))}</span>
            {o.team && <small>{teams[o.team].short_name}</small>}
            {reason && <span className="off-why" id={`${id}-${o.type}`}>{reason}</span>}
          </button>
        );
      })}
      {options.some((o) => !o.enabled) && (
        <p className="scn-off">
          {t("whatif.notHere", { list: options.filter((o) => !o.enabled).map((o) => `${optionLabel(o, t)} (${disabledReason(o, t)})`).join("; ") })}
        </p>
      )}
    </div>
  );
}

/** How far the run has got: done of 2 × n_runs, with the status in words for screen readers. */
export function RunProgress({ scenario }: { scenario: Scenario | null }) {
  const t = useT();
  const total = scenario ? totalRuns(scenario) : 0;
  const done = scenario ? Math.round(progressOf(scenario) * total) : 0;
  const status = scenario ? t(`whatif.status.${scenario.status}`) : t("whatif.status.starting");
  return (
    <div className="run-prog">
      <div className="run-head" role="status" aria-live="polite">
        <Stamp tone="live">{status}</Stamp>
        {scenario && <span className="num">{t("whatif.progress", { done: done.toLocaleString(numberLocale()), total: total.toLocaleString(numberLocale()) })}</span>}
      </div>
      <div
        className="run-bar"
        role="progressbar"
        aria-label={t("whatif.progressLabel")}
        aria-valuemin={0}
        aria-valuemax={total || undefined}
        aria-valuenow={scenario ? done : undefined}
      >
        <i style={{ width: `${scenario ? 100 * progressOf(scenario) : 0}%` }} className={scenario ? undefined : "wait"} />
      </div>
    </div>
  );
}

/** Why the run did not finish, in words the viewer can act on. */
export function failureText(error: unknown, t: T): string {
  if (error instanceof ApiError) {
    if (error.status === 404 || error.status === 422) return t("whatif.failed.rejected", { status: error.status });
    if ([502, 503, 504].includes(error.status) || !error.fromApi) return t("whatif.failed.unreachable");
  } else if (error instanceof TypeError) {
    return t("whatif.failed.unreachable");      // fetch could not reach the server
  }
  return t("whatif.failed.run");
}

export function RunFailed({ error, onRetry, onReset }: { error: unknown; onRetry: () => void; onReset: () => void }) {
  const t = useT();
  return (
    <div className="run-failed" role="alert">
      <b>{t("whatif.failed.title")}</b>
      <p>{failureText(error, t)}</p>
      <div className="comp-row">
        <Button variant="primary" onClick={onRetry}>{t("whatif.retryRun")}</Button>
        <Button variant="ghost" onClick={onReset}>{t("whatif.tryAnother")}</Button>
      </div>
    </div>
  );
}

/** One three-part bar, with every share and its 95% range written underneath. */
export function Distribution({ label, dist, teams, significant, ranges = true }: {
  label: string; dist: OutcomeDist; teams: Teams; significant?: SimResult["significant"];
  /** C13 QA: a fan gets the bar alone, no 95% ranges under it. */
  ranges?: boolean;
}) {
  const t = useT();
  return (
    <div className="dist">
      <span className="label muted">{label}</span>
      <div className="row" aria-hidden="true">
        {OUTCOMES.map((k) => (
          <i key={k} className={`${SEG_CLASS[k]}${pct(dist[k]) < 18 ? " tight" : ""}${significant?.[k] ? " sig" : ""}`} style={{ width: at(dist[k]) }}>
            {outcomeShort(k, teams, t)} {pct(dist[k])}%
          </i>
        ))}
      </div>
      {ranges && <span className="ci">
        {OUTCOMES.map((k) => {
          const [lo, hi] = ci(dist, k);
          return (
            <span key={k}>
              {significant?.[k] && <b className="sig-mark" aria-hidden="true">◆ </b>}
              {outcomeShort(k, teams, t)} {pct(dist[k])}% ({pct(lo)}–{pct(hi)})
            </span>
          );
        })}
      </span>}
    </div>
  );
}

/** Each outcome's two 95% ranges on one 0–100% line: where they stop overlapping, the change is clear. */
export function Ranges({ result, teams }: { result: Pick<SimResult, "baseline" | "counterfactual" | "significant">; teams: Teams }) {
  const t = useT();
  const band = (d: OutcomeDist, k: Outcome, cls: string) => {
    const [lo, hi] = ci(d, k);
    return (
      <>
        <i className={`band ${cls}`} style={{ left: at(lo), width: at(Math.max(0.006, hi - lo)) }} />
        <i className={`pt ${cls}`} style={{ left: at(d[k]) }} />
      </>
    );
  };
  return (
    <div className="ranges">
      <span className="label muted">{t("whatif.ranges")} <small>{t("whatif.rangesNote")}</small></span>
      <ul>
        {OUTCOMES.map((k) => {
          const [b, a] = [ci(result.baseline, k), ci(result.counterfactual, k)];
          const text = t("whatif.rangeRow", {
            outcome: outcomeShort(k, teams, t), before: pct(result.baseline[k]), blo: pct(b[0]), bhi: pct(b[1]),
            after: pct(result.counterfactual[k]), alo: pct(a[0]), ahi: pct(a[1]),
          });
          return (
            <li key={k} aria-label={result.significant[k] ? `${text}. ${t("whatif.significant")}` : text}>
              <span className="k" aria-hidden="true">{outcomeShort(k, teams, t)}</span>
              <span className="track" aria-hidden="true">
                {band(result.baseline, k, "was")}
                {band(result.counterfactual, k, "now")}
              </span>
              <span className="s" aria-hidden="true">{result.significant[k] ? "◆" : ""}</span>
            </li>
          );
        })}
      </ul>
      {OUTCOMES.some((k) => result.significant[k]) && <span className="ci">{t("whatif.sigMark")}</span>}
    </div>
  );
}

const ROWS: { key: MessageKey; of: (s: ArmStats["home"]) => Spread; digits: number }[] = [
  { key: "whatif.arms.shots", of: (s) => s.shots, digits: 1 },
  { key: "whatif.arms.onTarget", of: (s) => s.shots_on_target, digits: 1 },
  { key: "whatif.arms.xg", of: (s) => s.xg, digits: 2 },
  { key: "whatif.arms.red", of: (s) => s.red_cards, digits: 2 },
];

/** The two arms next to each other (Bx10): their likeliest final scores, then each side's numbers from the replay start. */
export function ArmCompare({ was, now, teams, from }: { was: ArmStats; now: ArmStats; teams: Teams; from: string }) {
  const t = useT();
  const scores = (a: ArmStats) => (
    <ul className="scores">
      {a.top_scores.slice(0, 3).map((s) => (
        <li key={scoreText(s)} aria-label={t("whatif.arms.scoreShare", { score: scoreText(s), share: pct(s.share) })}>
          <b>{scoreText(s)}</b> <small>{pct(s.share)}%</small>
        </li>
      ))}
    </ul>
  );
  const pair = (a: ArmStats, row: (typeof ROWS)[number]) =>
    `${row.of(a.home).mean.toFixed(row.digits)} – ${row.of(a.away).mean.toFixed(row.digits)}`;
  return (
    <div className="arms">
      <span className="label muted">{t("whatif.arms.title")} <small>{t("whatif.arms.note", { minute: from })}</small></span>
      <table className="ba">
        <thead>
          <tr>
            <th>{t("whatif.arms.teams", { home: teams.home.short_name, away: teams.away.short_name })}</th>
            <th>{t("whatif.arms.asPlayed")}</th>
            <th>{t("whatif.arms.changed")}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{t("whatif.arms.scores")}</td>
            <td>{scores(was)}</td>
            <td>{scores(now)}</td>
          </tr>
          {ROWS.map((row) => (
            <tr key={row.key}>
              <td>{t(row.key)}</td>
              <td>{pair(was, row)}</td>
              <td>{pair(now, row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** What one change means, in a line a fan can read (Ax91): shown under each change on the fan's cards. */
export function meaningOf(o: ScenarioOption, t: T, at: string | null): string {
  switch (o.type) {
    case "remove_goal":
    case "remove_red_card":
    case "cancel_substitution":
      return t(`wi.mean.${o.type}`);
    case "move_substitution": {
      const m = typeof o.params.new_minute === "number" ? String(o.params.new_minute + 1) : at ?? "";
      return t("wi.mean.move_substitution", { minute: m });
    }
    case "change_press":
      return t(/lower/i.test(o.label) ? "wi.mean.change_press.lower" : "wi.mean.change_press.higher");
    default:
      return t("wi.mean.other");
  }
}

type AnswerProps = {
  scenario: Scenario & { result: SimResult };
  /** The change in words ("Disallow 17′ goal"), its minute for the sentence, and the press direction. */
  change: string;
  minute: string | null;
  pressLower?: boolean;
  teams: Teams;
  /** The tab's first answer: an analyst gets the headline numbers there, and the full breakdown in the lab. */
  compact?: boolean;
};

/**
 * The answer to one what-if, in the viewer's version (Ax91). A fan gets one sentence, the chance that
 * matters to them before and after in big numbers, the three-way bars and the likeliest score. An
 * analyst gets the points moved and the significance label, the bars with their 95% ranges, the
 * likeliest scorelines, the team numbers with their spread, and how it was run.
 */
export function WhatIfAnswer(props: AnswerProps) {
  const { fan } = usePersona();
  return fan ? <FanAnswer {...props} /> : <AnalystAnswer {...props} />;
}

function useStory({ scenario, change, minute, pressLower, teams }: AnswerProps, side: "home" | "away" | null = null) {
  const t = useT();
  return storyLine({ result: scenario.result, type: scenario.spec.type, minute, change, pressLower, teams, side }, t);
}

function FanAnswer(props: AnswerProps) {
  const t = useT();
  const { side } = usePersona();
  const { minute } = useClock();
  const { scenario, teams } = props;
  const r = scenario.result;
  const story = useStory(props, side);
  // With a ♥ team, its chance of winning; otherwise the outcome that moved most.
  const focus: Outcome = side ? `${side}_win` : biggestShift(r).outcome;
  const team = focus === "draw" ? null : focus === "home_win" ? "home" : "away";
  const [was, now] = [pct(r.baseline[focus]), pct(r.counterfactual[focus])];
  const label = team === null ? t("wi.fan.drawChance") : possessive(t("wi.fan.winChance", { team: teams[team].name }));
  const delta = now - was;
  const top = (a: ArmStats | null | undefined) => a?.top_scores[0];
  const [scoreWas, scoreNow] = [top(r.baseline_stats), top(r.counterfactual_stats)];
  const from = minute(scenario.spec.at_minute);
  return (
    <div className="wi-fan">
      <p className="wi-fan-line">{story}</p>
      <div className="wi-fan-big" style={{ "--tc": team ? `var(--pv-${team})` : "var(--pv-ink-2)" } as CSSProperties}>
        <span className="wi-fan-label">
          {side && team === side && <b className="wi-fan-you">{t("wi.fan.yourTeam")}</b>}
          {label}
        </span>
        <div className="wi-fan-pair">
          <div>
            <span>{t("wi.fan.asPlayed")}</span>
            <b className="num">{was}%</b>
          </div>
          <div className="now">
            <span>{t("wi.fan.withChange")}</span>
            <b className="num">{now}%</b>
          </div>
          <p className="wi-fan-move">
            {t(delta === 0 ? "wi.fan.same" : team === null ? (delta > 0 ? "wi.fan.upDraw" : "wi.fan.downDraw") : delta > 0 ? "wi.fan.up" : "wi.fan.down", { n: Math.abs(delta) })}
          </p>
        </div>
      </div>
      <div className="wi-fan-who">
        <span className="wi-fan-label">{t("wi.fan.who")}</span>
        <div className="dists">
          <Distribution label={t("wi.fan.asPlayedFrom", { minute: from })} dist={r.baseline} teams={teams} ranges={false} />
          <Distribution label={t("wi.fan.withChange")} dist={r.counterfactual} teams={teams} ranges={false} />
        </div>
      </div>
      {scoreWas && scoreNow && (
        <div className="wi-fan-score">
          <span className="wi-fan-label">{t("wi.fan.score")}</span>
          <dl>
            <div>
              <dt>{t("wi.fan.asPlayed")}</dt>
              <dd><Score s={scoreWas} teams={teams} /></dd>
            </div>
            <div className="now">
              <dt>{t("wi.fan.withChange")}</dt>
              <dd><Score s={scoreNow} teams={teams} /></dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  );
}

/** "TES 1–0 VAN", the numbers big. */
function Score({ s, teams }: { s: ScoreShare; teams: Teams }) {
  return (
    <span className="wi-score">
      <small>{teams.home.short_name}</small>
      <b className="num">{scoreText(s)}</b>
      <small>{teams.away.short_name}</small>
    </span>
  );
}

function AnalystAnswer(props: AnswerProps) {
  const t = useT();
  const { minute } = useClock();
  const { side } = usePersona();
  const { scenario, teams, change } = props;
  const r = scenario.result;
  const shift = biggestShift(r);
  const story = useStory(props);
  const from = minute(scenario.spec.at_minute);
  return (
    <div className="wi-an">
      <div className={`verdict${shift.significant ? "" : " flat"}`}>
        <span className="big num">
          {shift.points > 0 ? "+" : shift.points < 0 ? "−" : "±"}{Math.abs(shift.points)}<small>{t("whatif.pts")}</small>
        </span>
        <span className="t">
          {story}
          <br />
          <Stamp tone={shift.significant ? "ok" : "line"}>{t(shift.significant ? "whatif.significant" : "whatif.notSignificant")}</Stamp>
        </span>
      </div>
      <div className="dists">
        <Distribution label={t("whatif.asPlayed", { minute: from })} dist={r.baseline} teams={teams} />
        <Distribution label={t("whatif.changed", { change })} dist={r.counterfactual} teams={teams} significant={r.significant} />
      </div>
      {side && (
        <p className="wi-you" style={{ "--tc": `var(--pv-${side})` } as CSSProperties}>
          {possessive(t("whatif.forYou", { team: teams[side].name, was: pct(r.baseline[`${side}_win`]), now: pct(r.counterfactual[`${side}_win`]) }))}
        </p>
      )}
      <Effect r={r} n={scenario.spec.n_runs} teams={teams} />
      <Ranges result={r} teams={teams} />
      {props.compact ? null : r.baseline_stats && r.counterfactual_stats ? (
        <>
          <div className="wi-an-pair">
            <ScoreMatrices was={r.baseline_stats} now={r.counterfactual_stats} teams={teams} />
            <StatForest was={r.baseline_stats} now={r.counterfactual_stats} teams={teams} />
          </div>
          <StatDeltas was={r.baseline_stats} now={r.counterfactual_stats} teams={teams} from={from} />
        </>
      ) : (
        <p className="fine">{t("wi.an.noStats")}</p>
      )}
      {!props.compact && <Method scenario={scenario} from={from} />}
    </div>
  );
}

/** A standard normal's distribution function (Abramowitz–Stegun 7.1.26), for the chance a change helps. */
const phi = (z: number) => {
  const x = Math.abs(z) / Math.SQRT2;
  const k = 1 / (1 + 0.3275911 * x);
  const erf = 1 - (((((1.061405429 * k - 1.453152027) * k) + 1.421413741) * k - 0.284496736) * k + 0.254829592) * k * Math.exp(-x * x);
  return z >= 0 ? (1 + erf) / 2 : (1 - erf) / 2;
};

/**
 * The effect in numbers (Ax91), read off the two outcome shares and the run count. The arms are
 * paired by seed, but the stored result keeps no per-run pairs, so the intervals treat them as
 * independent: wider than the paired ones, so on the safe side.
 */
export function effectOf(r: Pick<SimResult, "baseline" | "counterfactual">, n: number, outcome: Outcome) {
  const [p0, p1] = [r.baseline[outcome], r.counterfactual[outcome]];
  const se = Math.sqrt((p0 * (1 - p0)) / n + (p1 * (1 - p1)) / n) || 1e-9;
  const d = p1 - p0;
  return { points: 100 * d, lo: 100 * (d - 1.96 * se), hi: 100 * (d + 1.96 * se), helps: phi(d / se) };
}

/** Expected points for one side (3 a win, 1 a draw) and its 95% interval over n runs. */
export function expectedPoints(d: OutcomeDist, side: "home" | "away", n: number) {
  const w = d[`${side}_win`];
  const mean = 3 * w + d.draw;
  const sd = Math.sqrt(Math.max(0, 9 * w + d.draw - mean * mean));
  return { mean, lo: mean - (1.96 * sd) / Math.sqrt(n), hi: mean + (1.96 * sd) / Math.sqrt(n) };
}

function Effect({ r, n, teams }: { r: SimResult; n: number; teams: Teams }) {
  const t = useT();
  const { side } = usePersona();
  const { outcome } = biggestShift(r);
  const team = side ?? (outcome === "away_win" ? "away" : "home");
  const focus: Outcome = side ? `${side}_win` : outcome;
  const e = effectOf(r, n, focus);
  const [x0, x1] = [expectedPoints(r.baseline, team, n), expectedPoints(r.counterfactual, team, n)];
  const loc = numberLocale();
  const signed = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v).toLocaleString(loc, { maximumFractionDigits: 1, minimumFractionDigits: 1 })}`;
  const f2 = (v: number) => v.toLocaleString(loc, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const helps = e.points >= 0 ? e.helps : 1 - e.helps;
  const what = focus === "draw" ? t("wi.an.eff.draw") : t("wi.an.eff.win", { team: teams[focus === "home_win" ? "home" : "away"].short_name });
  return (
    <dl className="open-facts wi-effect">
      <div title={t("wi.an.eff.effectHow")}>
        <dt>{t("wi.an.eff.effect", { what })}</dt>
        <dd className="num">{t("wi.an.eff.effectValue", { pts: signed(e.points), lo: signed(e.lo), hi: signed(e.hi) })}</dd>
      </div>
      <div title={t("wi.an.eff.helpsHow")}>
        <dt>{t(e.points >= 0 ? "wi.an.eff.helps" : "wi.an.eff.hurts", { what })}</dt>
        <dd className="num">{helps > 0.999 ? t("wi.an.eff.over") : `${(100 * helps).toLocaleString(loc, { maximumFractionDigits: 1 })}%`}</dd>
      </div>
      <div title={t("wi.an.eff.xptsHow")}>
        <dt>{t("wi.an.eff.xpts", { team: teams[team].short_name })}</dt>
        <dd className="num">{t("wi.an.eff.xptsValue", { was: f2(x0.mean), wlo: f2(x0.lo), whi: f2(x0.hi), now: f2(x1.mean), nlo: f2(x1.lo), nhi: f2(x1.hi) })}</dd>
      </div>
    </dl>
  );
}

const GOALS = [0, 1, 2, 3, 4] as const;

/**
 * The likeliest final scores as two home × away goal grids (Ax91), shaded by share. The result keeps
 * only the five likeliest scores of each arm, so the other cells stay empty and the note says so.
 */
export function ScoreMatrices({ was, now, teams }: { was: ArmStats; now: ArmStats; teams: Teams }) {
  const t = useT();
  const most = Math.max(...[...was.top_scores, ...now.top_scores].map((s) => s.share), 0.01);
  const grid = (a: ArmStats, label: string, cls: string) => {
    const at = (h: number, w: number) => a.top_scores.find((s) => s.home === h && s.away === w);
    const top = a.top_scores[0];
    return (
      <figure className={`wi-mx ${cls}`}>
        <figcaption>{label}</figcaption>
        <table aria-label={label}>
          <thead>
            <tr>
              <th scope="col"><span className="sr-only">{t("wi.an.mx.corner", { home: teams.home.short_name, away: teams.away.short_name })}</span></th>
              {GOALS.map((w) => <th key={w} scope="col" className="num">{w}</th>)}
            </tr>
          </thead>
          <tbody>
            {GOALS.map((h) => (
              <tr key={h}>
                <th scope="row" className="num">{h}</th>
                {GOALS.map((w) => {
                  const s = at(h, w);
                  return (
                    <td key={w} className={s && top && s === top ? "top" : undefined}
                      style={s ? ({ "--a": (s.share / most).toFixed(2) } as CSSProperties) : undefined}
                      aria-label={s ? t("whatif.arms.scoreShare", { score: scoreText(s), share: pct(s.share) }) : undefined}>
                      {s ? <span className="num">{pct(s.share)}</span> : null}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </figure>
    );
  };
  return (
    <div className="wi-an-block">
      <h3 className="wi-an-hd">{t("wi.an.scores")} <small>{t("wi.an.mx.axes", { home: teams.home.short_name, away: teams.away.short_name })}</small></h3>
      <div className="wi-mxs">
        {grid(was, t("whatif.arms.asPlayed"), "was")}
        {grid(now, t("whatif.arms.changed"), "now")}
      </div>
      <p className="fine">{t("wi.an.mx.note", { n: was.top_scores.length })}</p>
    </div>
  );
}

const STATS: { key: MessageKey; of: (s: ArmStats["home"]) => Spread; digits: number }[] = [
  { key: "wi.an.goals", of: (s) => s.goals, digits: 2 },
  { key: "whatif.arms.shots", of: (s) => s.shots, digits: 1 },
  { key: "whatif.arms.onTarget", of: (s) => s.shots_on_target, digits: 1 },
  { key: "whatif.arms.xg", of: (s) => s.xg, digits: 2 },
  { key: "wi.an.possession", of: (s) => s.possession_pct, digits: 1 },
  { key: "wi.an.cards", of: (s) => s.cards, digits: 2 },
  { key: "whatif.arms.red", of: (s) => s.red_cards, digits: 2 },
];

/** Each side's numbers from the replay start, both arms with their 10th–90th percentile and the change in the mean. */
export function StatDeltas({ was, now, teams, from }: { was: ArmStats; now: ArmStats; teams: Teams; from: string }) {
  const t = useT();
  const loc = numberLocale();
  const f = (n: number, d: number) => n.toLocaleString(loc, { minimumFractionDigits: d, maximumFractionDigits: d });
  const spread = (s: Spread, d: number) => (
    <>
      <span className="num">{f(s.mean, d)}</span> <small className="num muted">({f(s.p10, Math.min(d, 1))}–{f(s.p90, Math.min(d, 1))})</small>
    </>
  );
  return (
    <div className="wi-an-block">
      <h3 className="wi-an-hd">{t("wi.an.stats", { minute: from })} <small>{t("wi.an.statsNote")}</small></h3>
      <table className="ba wi-table wi-stats">
        <thead>
          <tr>
            <th scope="col">{t("wi.an.stat")}</th>
            <th scope="col">{t("wi.an.team")}</th>
            <th scope="col">{t("whatif.arms.asPlayed")}</th>
            <th scope="col">{t("whatif.arms.changed")}</th>
            <th scope="col">{t("wi.an.diff")}</th>
          </tr>
        </thead>
        <tbody>
          {STATS.flatMap((row) => (["home", "away"] as const).map((side, i) => {
            const [a, b] = [row.of(was[side]), row.of(now[side])];
            const d = b.mean - a.mean;
            const shown = f(Math.abs(d), row.digits);
            return (
              <tr key={`${row.key}-${side}`} className={i ? "second" : undefined}>
                {i === 0 && <th scope="rowgroup" rowSpan={2}>{t(row.key)}</th>}
                <td className="tm"><span className="wi-kit" style={{ "--tc": `var(--pv-${side})` } as CSSProperties}>{teams[side].short_name}</span></td>
                <td>{spread(a, row.digits)}</td>
                <td>{spread(b, row.digits)}</td>
                <td className="num">{Number(shown) === 0 || /^0([.,]0+)?$/.test(shown) ? "0" : `${d > 0 ? "+" : "−"}${shown}`}</td>
              </tr>
            );
          }))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Each side's change in every number as a forest plot (Ax91): the dot is the change in the mean in
 * standard deviations of the as-played runs, the line its 95% interval, the middle line no change.
 */
export function StatForest({ was, now, teams }: { was: ArmStats; now: ArmStats; teams: Teams }) {
  const t = useT();
  const loc = numberLocale();
  const n = Math.max(1, Math.min(was.n_runs, now.n_runs));
  const LIM = 1;                                 // ±1 standard deviation across the plot
  const x = (v: number) => `${50 + (50 * Math.max(-LIM, Math.min(LIM, v))) / LIM}%`;
  const rows = STATS.filter((r) => r.key !== "whatif.arms.red").flatMap((row) => (["home", "away"] as const).map((side) => {
    const [a, b] = [row.of(was[side]), row.of(now[side])];
    const unit = a.sd || b.sd || 1;
    const se = Math.sqrt((a.sd ** 2 + b.sd ** 2) / n);
    const d = b.mean - a.mean;
    return { key: `${row.key}-${side}`, label: t(row.key), side, d, mid: d / unit, lo: (d - 1.96 * se) / unit, hi: (d + 1.96 * se) / unit,
      clear: d - 1.96 * se > 0 || d + 1.96 * se < 0, digits: row.digits };
  }));
  const signed = (v: number, dg: number) => `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v).toLocaleString(loc, { minimumFractionDigits: dg, maximumFractionDigits: dg })}`;
  return (
    <div className="wi-an-block">
      <h3 className="wi-an-hd">{t("wi.an.forest")} <small>{t("wi.an.forestNote")}</small></h3>
      <ul className="wi-forest">
        {rows.map((r) => (
          <li key={r.key} style={{ "--tc": `var(--pv-${r.side})` } as CSSProperties}
            aria-label={t("wi.an.forestRow", { stat: r.label, team: teams[r.side].short_name, d: signed(r.d, r.digits) })}>
            <span className="k" aria-hidden="true">{r.label} <small>{teams[r.side].short_name}</small></span>
            <span className="track" aria-hidden="true">
              <i className="ci" style={{ left: x(r.lo), width: `calc(${x(r.hi)} - ${x(r.lo)})` }} />
              <i className={`pt${r.clear ? " clear" : ""}`} style={{ left: x(r.mid) }} />
            </span>
            <span className="v num" aria-hidden="true">{signed(r.d, r.digits)}</span>
          </li>
        ))}
      </ul>
      <div className="wi-forest-axis" aria-hidden="true">
        <span>{t("wi.an.forestLess")}</span><span>0</span><span>{t("wi.an.forestMore")}</span>
      </div>
    </div>
  );
}

/** How the answer was made: the snapshot, the runs and seeds, the time, and what the ranges are. */
function Method({ scenario, from }: { scenario: Scenario & { result: SimResult }; from: string }) {
  const t = useT();
  const loc = numberLocale();
  const n = scenario.spec.n_runs;
  return (
    <div className="wi-an-block">
      <h3 className="wi-an-hd">{t("wi.an.method")}</h3>
      <dl className="open-facts wi-method">
        <div><dt>{t("wi.an.m.from")}</dt><dd>{t("whatif.confirm.fromValue", { minute: from })}</dd></div>
        <div><dt>{t("wi.an.m.runs")}</dt><dd className="num">{t("wi.an.m.runsValue", { n: n.toLocaleString(loc), total: (2 * n).toLocaleString(loc) })}</dd></div>
        <div><dt>{t("wi.an.m.seeds")}</dt><dd className="num">{t("wi.an.m.seedsValue", { seed: String(scenario.spec.seed_base) })}</dd></div>
        <div><dt>{t("wi.an.m.time")}</dt><dd className="num">{t("wi.an.m.timeValue", { s: (scenario.result.runtime_ms / 1000).toLocaleString(loc, { maximumFractionDigits: 1 }) })}</dd></div>
      </dl>
      <p className="fine">{t("wi.an.m.note")}</p>
    </div>
  );
}

type ResultProps = {
  state: Extract<RunState, { phase: "done" }>;
  /** The chip that was run, for its label. */
  option: ScenarioOption | undefined;
  teams: Teams;
  onReset: () => void;
  /** Where to ask for the comparison in the page's language when the run's own one is in another (Ax39). */
  source: ScenarioApi;
};

export function ScenarioResult({ state, option, teams, onReset, source }: ResultProps) {
  const { prefs, t } = usePrefs();
  const minuteOf = useOptionMinute();
  const { minute } = useClock();
  const { scenario, cached } = state;
  const n = scenario.spec.n_runs;
  const from = minute(scenario.spec.at_minute);
  // Ax91: a fan and an analyst get different answers; see WhatIfAnswer.
  const { fan } = usePersona();
  const moveTo = typeof scenario.spec.params.new_minute === "number" ? scenario.spec.params.new_minute + 1 : undefined;
  const change = option ? optionLabel(option, t, moveTo, minuteOf(option)) : scenario.spec.type;
  const { narrative, writing } = useComparisonIn(source, scenario, prefs.language);
  const served = narrativeLang(narrative);
  // Ax91: a fan reads the headline and the first line; the rest (often the template's shot counts) is an analyst's.
  const sentences = (narrative?.sentences ?? []).slice(0, fan ? 1 : undefined);
  return (
    <div className="result">
      <div className="stamps">
        {fan ? (
          <Stamp tone="warn">{t("whatif.simulated")}</Stamp>
        ) : (
          <>
            <Stamp tone="warn">{t("whatif.stamp", { n: n.toLocaleString(numberLocale()) })}</Stamp>
            {cached && <Stamp tone="line">{t("whatif.cached")}</Stamp>}
          </>
        )}
      </div>
      <WhatIfAnswer scenario={scenario} change={change} minute={option ? minuteOf(option) : from}
        pressLower={!!option && /lower/i.test(option.label)} teams={teams} />
      <div className="why">
        <span className="label muted">{t("whatif.comparison")}</span>
        {narrative ? (
          <>
            {writing && served && (
              <div className="lang-note" role="note">
                {t("why.writing", { wanted: t(`lang.${prefs.language}`), served: t(`lang.${served}`) })}
              </div>
            )}
            <p lang={served ?? undefined}><b>{possessive(scoreDashes(narrative.headline))}</b> <LangTag lang={served} /></p>
            {sentences.map((s, i) => <p key={i} lang={served ?? undefined}>{possessive(scoreDashes(s.text))}</p>)}
          </>
        ) : (
          <p className="muted">{t("whatif.noNarrative")}</p>
        )}
      </div>
      <div className="comp-row">
        <Button onClick={onReset}>{t("whatif.tryAnother")}</Button>
      </div>
    </div>
  );
}
