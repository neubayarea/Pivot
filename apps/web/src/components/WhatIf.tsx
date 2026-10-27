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
/** "1-2" becomes "1–2" in a sentence (C13 QA); a formation like 4-3-3 is left alone. */
export const scoreDashes = (text: string) => text.replace(/(?<![\d-])(\d{1,2})-(\d{1,2})(?![\d-])/g, "$1–$2");

/** A team name ending in s takes a bare apostrophe: "Northgate Rovers’ chance", not "Rovers’s". */
const possessive = (text: string) => text.replace(/s’s/g, "s’");

export function storyLine(input: StoryInput, t: T): string {
  const { result: r, teams } = input;
  const { outcome } = biggestShift(r);
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

/** One button per scenario; unavailable ones stay focusable and say why, rather than vanishing. */
export function ScenarioChips({ options, selected, onSelect, teams, moveTo }: ChipsProps) {
  const t = useT();
  const minuteOf = useOptionMinute();
  const id = useId();
  return (
    <div className="scn" role="group" aria-label={t("whatif.pickLabel")}>
      {options.map((o) => {
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
  const r = scenario.result;
  const n = scenario.spec.n_runs;
  const shift = biggestShift(r);
  const from = minute(scenario.spec.at_minute);
  // C12: a fan gets the sentence and the two big bars; an analyst also the ranges and the score and shot tables.
  // With a ♥ team, one line says what the change did to its chance of winning.
  const { fan, side } = usePersona();
  const moveTo = typeof scenario.spec.params.new_minute === "number" ? scenario.spec.params.new_minute + 1 : undefined;
  const change = option ? optionLabel(option, t, moveTo, minuteOf(option)) : scenario.spec.type;
  const { narrative, writing } = useComparisonIn(source, scenario, prefs.language);
  const served = narrativeLang(narrative);
  const sentences = narrative?.sentences ?? [];
  return (
    <div className="result">
      <div className="stamps">
        <Stamp tone="warn">{t("whatif.stamp", { n: n.toLocaleString(numberLocale()) })}</Stamp>
        {cached && !fan && <Stamp tone="line">{t("whatif.cached")}</Stamp>}
      </div>
      <div className={`verdict${shift.significant ? "" : " flat"}`}>
        {/* C13 QA: a fan gets the sentence; the points and the significance stamp are an analyst's. */}
        {!fan && (
          <span className="big num">
            {shift.points > 0 ? "+" : shift.points < 0 ? "−" : "±"}{Math.abs(shift.points)}<small>{t("whatif.pts")}</small>
          </span>
        )}
        <span className="t">
          {storyLine({ result: r, type: scenario.spec.type, minute: option ? minuteOf(option) : from, change,
            pressLower: !!option && /lower/i.test(option.label), teams }, t)}
          {!fan && (
            <>
              <br />
              <Stamp tone={shift.significant ? "ok" : "line"}>{t(shift.significant ? "whatif.significant" : "whatif.notSignificant")}</Stamp>
            </>
          )}
        </span>
      </div>
      <div className="dists">
        <Distribution label={t("whatif.asPlayed", { minute: from })} dist={r.baseline} teams={teams} ranges={!fan} />
        <Distribution label={t("whatif.changed", { change })} dist={r.counterfactual} teams={teams} significant={r.significant} ranges={!fan} />
      </div>
      {side && (
        <p className="wi-you" style={{ "--tc": `var(--pv-${side})` } as CSSProperties}>
          {possessive(t("whatif.forYou", { team: teams[side].name, was: pct(r.baseline[`${side}_win`]), now: pct(r.counterfactual[`${side}_win`]) }))}
        </p>
      )}
      {!fan && r.baseline_stats && r.counterfactual_stats && (
        <ArmCompare was={r.baseline_stats} now={r.counterfactual_stats} teams={teams} from={from} />
      )}
      {!fan && <Ranges result={r} teams={teams} />}
      <div className="why">
        <span className="label muted">{t("whatif.comparison")}</span>
        {narrative ? (
          <>
            {writing && served && (
              <div className="lang-note" role="note">
                {t("why.writing", { wanted: t(`lang.${prefs.language}`), served: t(`lang.${served}`) })}
              </div>
            )}
            <p lang={served ?? undefined}><b>{narrative.headline}</b> <LangTag lang={served} /></p>
            {sentences.map((s, i) => <p key={i} lang={served ?? undefined}>{scoreDashes(s.text)}</p>)}
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
