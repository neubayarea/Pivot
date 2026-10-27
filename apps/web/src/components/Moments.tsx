// The board's numbered moments (Ax32): one card per pivot, and the one picked opened up with its
// explanation, the pitch at that moment and the what-if chips. Layout follows docs/design/redesign-mockup.html.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { useFrames } from "../data/live/frames";
import { fixtureMode, useMatch } from "../data/match";
import { optionLabel, useOptionMinute, useScenarioRun, type ScenarioOption } from "../data/scenarios";
import { useT } from "../i18n";
import { detailFrame } from "../pages/PivotDetail";
import { useScenarioSource } from "../pages/WhatIfLab";
import Button from "./Button";
import { describe } from "./EventFeed";
import Pitch, { whoFromSquads } from "./Pitch";
import { PivotStamp, pivotHeadline } from "./PivotList";
import { RunFailed, RunProgress, ScenarioResult } from "./WhatIf";
import WhyItTurned from "./WhyItTurned";

/** What set the pivot off, as the event list says it: "38′ Red card · Lisais". Null without a trigger. */
export function useCause(p: Pivot): string | null {
  const { eventById, playerName } = useMatch();
  const t = useT();
  const e = p.trigger_event_ids.map(eventById).find(Boolean);
  return e ? `${e.clock_label.replace(/'$/, "′")} ${describe(e, playerName, t)}` : null;
}

const SW = 96, SH = 32, SPAN = 8;

/** The momentum line eight minutes either side of the pivot, in the two kits: the swing at a glance. */
function Swing({ p }: { p: Pivot }) {
  const { metrics } = useMatch();
  const near = metrics.filter((m) => m.minute >= p.minute - SPAN && m.minute <= p.minute + SPAN);
  if (near.length < 3) return null;
  const x = (m: number) => ((m - (p.minute - SPAN)) / (2 * SPAN)) * SW;
  const y = (v: number) => SH / 2 - Math.max(-1, Math.min(1, v)) * (SH / 2 - 1);
  const area = `M${x(near[0].minute)},${SH / 2}${near.map((m) => ` L${x(m.minute)},${y(m.momentum)}`).join("")} L${x(near.at(-1)!.minute)},${SH / 2} Z`;
  const clip = `sw-${p.pivot_id.replace(/[^\w-]/g, "")}`;
  return (
    <svg className="pr-swing" viewBox={`0 0 ${SW} ${SH}`} width={SW} height={SH} aria-hidden="true">
      <defs>
        <clipPath id={`${clip}u`}><rect x={0} y={0} width={SW} height={SH / 2} /></clipPath>
        <clipPath id={`${clip}d`}><rect x={0} y={SH / 2} width={SW} height={SH / 2} /></clipPath>
      </defs>
      <path d={area} className="home" clipPath={`url(#${clip}u)`} />
      <path d={area} className="away" clipPath={`url(#${clip}d)`} />
      <line x1={0} x2={SW} y1={SH / 2} y2={SH / 2} className="mid" />
      <line x1={x(p.minute)} x2={x(p.minute)} y1={0} y2={SH} className="at" />
    </svg>
  );
}

function MomentRow({ p, n, on, onPick }: { p: Pivot; n: number; on: boolean; onPick: () => void }) {
  const { teams } = useMatch();
  const t = useT();
  const { minute } = useClock();
  const cause = useCause(p);
  return (
    <button type="button" className={`pr to-${p.direction}`} aria-pressed={on} onClick={onPick}>
      <span className="pr-n" aria-hidden="true">{n}</span>
      <b className="pr-min num">{minute(p.minute)}′</b>
      <span className="pr-txt">
        <span className="pr-hd">{pivotHeadline(p, teams, t)}</span>
        {cause && <span className="pr-cause">{t("moments.cause", { cause })}</span>}
      </span>
      <span className="pr-sw">
        <Swing p={p} />
        <span className="to">{t("post.swingTo", { team: teams[p.direction].name })}</span>
      </span>
      <span className="pr-st"><PivotStamp status={p.status} /></span>
      <span className="pr-chev" aria-hidden="true" />
    </button>
  );
}

/** The pivots as the story of the match, one line each; the one picked opens right under its line. */
export function MomentCards({ pivots, selected, onPick, open }: {
  pivots: Pivot[]; selected: string | null; onPick: (id: string) => void; open?: ReactNode;
}) {
  return (
    <ol className="pv-story">
      {pivots.map((p, i) => (
        <li key={p.pivot_id} className={p.pivot_id === selected ? "on" : undefined}>
          <MomentRow p={p} n={i + 1} on={p.pivot_id === selected} onPick={() => onPick(p.pivot_id)} />
          {p.pivot_id === selected && open}
        </li>
      ))}
    </ol>
  );
}

/** The pitch at the moment: the first piece of evidence with a place, or the one the viewer clicked. */
function MomentPitch({ pivot, picked }: { pivot: Pivot; picked: string | null }) {
  const { match, squads, pivotDetail, eventById, playerName } = useMatch();
  const t = useT();
  const detail = pivotDetail(pivot.pivot_id);
  const evidence = [...new Set((pivot.narrative?.sentences ?? []).flatMap((s) => s.evidence_ids))].flatMap((id) => eventById(id) ?? []);
  const shown = (picked ? eventById(picked) : undefined) ?? evidence.find((e) => e.location) ?? evidence[0];
  const [from, to] = detail?.window ?? [pivot.minute * 60, pivot.minute * 60];
  const at = Math.min(to, Math.max(from, shown?.t ?? pivot.minute * 60));
  const [fixture] = useState(() => typeof window === "undefined" || fixtureMode());
  const fetched = useFrames(fixture ? null : match.match_id, at);
  const who = useMemo(() => (fixture ? undefined : whoFromSquads(squads)), [fixture, squads]);
  if (!detail) return null;
  const { frame, note } = detailFrame(detail.frames, from, at, fetched);
  const actions = shown?.location ? [shown] : [];
  return (
    <figure className="mo-pitch">
      <Pitch frame={frame} actions={actions} selected={shown?.event_id ?? null} focus={null} who={who}
        label={t("detail.pitchLabel", { t: frame.t, n: frame.players.length })} />
      <figcaption>
        {shown && <><b>{shown.clock_label.replace(/'$/, "′")}</b> {describe(shown, playerName, t)}</>}
        {note && <span className="muted"> {t(note === "none" ? "board.pitchNone" : "board.pitchLoading")}</span>}
      </figcaption>
    </figure>
  );
}

/**
 * The what-if chips for one moment (the post-match tab's What-if section, Ax59). Picking a chip only says what would run; nothing is
 * simulated until the viewer presses Start (a real run takes minutes, a cached one answers at once).
 */
export function WhatIfInline({ pivot }: { pivot: Pivot }) {
  const { teams } = useMatch();
  const t = useT();
  const { minute } = useClock();
  const minuteOf = useOptionMinute();
  const source = useScenarioSource();
  const [options, setOptions] = useState<ScenarioOption[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [chosen, setChosen] = useState<ScenarioOption["type"] | null>(null);
  const { state, run, reset } = useScenarioRun(source);

  useEffect(() => {
    let alive = true;
    source.options(pivot.pivot_id).then((o) => alive && setOptions(o), () => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [source, pivot.pivot_id]);

  const enabled = (options ?? []).filter((o) => o.enabled).slice(0, 3);
  const option = enabled.find((o) => o.type === chosen);
  const busy = state.phase === "starting" || state.phase === "running";
  const pick = (type: ScenarioOption["type"]) => {
    if (state.phase !== "idle") reset();
    setChosen(type);
  };

  return (
    <section className="mo-wi" aria-label={t("detail.whatIf")}>
      <div className="mo-wi-hd">
        <h3>{t("detail.whatIf")}</h3>
        <p className="muted">{t("moments.wiNote")}</p>
      </div>
      {failed ? (
        <p className="muted">{t("whatif.optionsError")}</p>
      ) : !options ? (
        <p className="muted" role="status">{t("whatif.loadingOptions")}</p>
      ) : !enabled.length ? (
        <p className="muted">{t("whatif.noOptions")}</p>
      ) : (
        <div className="chips" role="group" aria-label={t("whatif.pickLabel")}>
          {enabled.map((o) => (
            <button key={o.type} type="button" className="chip" aria-pressed={o.type === chosen} onClick={() => pick(o.type)}>
              {optionLabel(o, t, undefined, minuteOf(o))}
              {o.team && <small>{teams[o.team].short_name}</small>}
            </button>
          ))}
        </div>
      )}
      <div className="mo-wi-res">
        {!option && enabled.length > 0 && <p className="muted">{t("moments.wiPick")}</p>}
        {option && state.phase === "idle" && (
          <div className="mo-wi-go">
            <p>
              <b>{optionLabel(option, t, undefined, minuteOf(option))}</b>
              {option.at_minute !== null && <small className="muted">{t("moments.wiHow", { minute: minute(option.at_minute) })}</small>}
            </p>
            <Button variant="primary" onClick={() => run({ pivot_id: pivot.pivot_id, type: option.type, n_runs: 200, ...(Object.keys(option.params).length ? { params: option.params } : {}) })}>
              {t("whatif.run")}
            </Button>
          </div>
        )}
        {busy && <RunProgress scenario={state.phase === "running" ? state.scenario : null} />}
        {state.phase === "failed" && <RunFailed error={state.error} onRetry={() => run(state.body, { fresh: true })} onReset={reset} />}
        {state.phase === "done" && <ScenarioResult state={state} option={option} teams={teams} onReset={() => { reset(); setChosen(null); }} source={source} />}
      </div>
      <Link to={`/whatif/${pivot.pivot_id}`} className="more-link">{t("moments.lab")}</Link>
    </section>
  );
}

/** The one moment opened up under its line: why it mattered and where everyone stood. What-if has its own section (Ax59). */
export function OpenMoment({ pivot, n, evidence, onEvidence }: {
  pivot: Pivot; n: number; evidence: ReadonlySet<string>; onEvidence: (id: string) => void;
}) {
  const t = useT();
  const { minute } = useClock();
  const picked = [...evidence].at(-1) ?? null;
  return (
    <section className="open-mo" aria-label={t("moments.open", { n, minute: minute(pivot.minute) })}>
      {pivot.status === "degraded" && (
        <div className="banner warn" role="status">
          {t("banner.degraded")}
        </div>
      )}
      <div className="open-bd">
        <WhyItTurned pivot={pivot} selected={evidence} onToggle={onEvidence} chipHint={t("moments.chipHint")} />
        <MomentPitch pivot={pivot} picked={picked} />
      </div>
      <Link to={`/pivot/${pivot.pivot_id}`} className="more-link">{t("moments.detail")}</Link>
    </section>
  );
}
