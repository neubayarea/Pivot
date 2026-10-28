// 假如 · What-if (C13 #316): the lab gets a tab of its own. A fan gets the ranked list in FanWhatIfs (Ax91). Pick a turning point here, then a change
// in the lab; the first turning point is open when the link names none (`&pivot=`). Each chip names
// its turning point, so the lab's own back link is not needed here.
import { useEffect, useState } from "react";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { RunProgress, WhatIfAnswer, scoreDashes } from "../../components/WhatIf";
import { pivotHeadline } from "../../components/PivotList";
import { useClock } from "../../data/clock";
import { useHeightVar } from "../../data/headerFold";
import { useMatch } from "../../data/match";
import { forYourTeam, usePersona } from "../../data/persona";
import { optionLabel, useOptionMinute, useScenarioRun, type ScenarioApi, type ScenarioOption } from "../../data/scenarios";
import { useT } from "../../i18n";
import { Lab, useScenarioSource } from "../WhatIfLab";
import { FanWhatIfs } from "./FanWhatIfs";

export function WhatIfTab({ moments, open, onPick }: { moments: Pivot[]; open: Pivot | null; onPick: (id: string) => void }) {
  const t = useT();
  const { teams } = useMatch();
  const { minute } = useClock();
  const source = useScenarioSource();
  // Ax77: the turning-point chips stick under the tabs.
  const row = useHeightVar("--pv-sub-h");
  const pivot = open ?? moments[0] ?? null;
  const { fan } = usePersona();
  if (!pivot) return <p className="muted">{t("post.whatIfNone")}</p>;
  // Ax91 (#431): a fan gets one ranked list of the match's biggest what-ifs, every turning point in it.
  if (fan) return <FanWhatIfs moments={moments} source={source} />;
  return (
    <>
      {moments.length > 1 && (
        <div ref={row} className="chips wi-pivots" role="group" aria-label={t("post.whatIfFor")}>
          {moments.map((p, i) => (
            <button key={p.pivot_id} type="button" className="chip" aria-pressed={p.pivot_id === pivot.pivot_id} onClick={() => onPick(p.pivot_id)}
              aria-label={t("post.whatIfAt", { n: i + 1, minute: minute(p.minute) })}>
              <span className="badge" aria-hidden="true">{i + 1}</span>
              <b className="num">{minute(p.minute)}′</b>
              <span className="wi-hd">{pivotHeadline(p, teams, t)}</span>
            </button>
          ))}
        </div>
      )}
      <Featured key={`f-${pivot.pivot_id}`} pivot={pivot} source={source} />
      <div className="wi-tab">
        <Lab key={pivot.pivot_id} pivotId={pivot.pivot_id} source={source} />
      </div>
    </>
  );
}

/** The most striking change first: a goal or a red card taken away, then a substitution, then the press. */
const STRIKING: ScenarioOption["type"][] = ["remove_goal", "remove_red_card", "cancel_substitution", "move_substitution", "change_press"];

/**
 * The tab's first screen (C13): one change already played out, the sentence and the two big bars,
 * before the viewer picks anything. With a ♥ team it is the change that would have helped that team.
 * A result run ahead (Bx14) answers at once; otherwise the usual progress shows while it runs.
 */
function Featured({ pivot, source }: { pivot: Pivot; source: ScenarioApi }) {
  const { teams } = useMatch();
  const t = useT();
  const { side } = usePersona();
  const minuteOf = useOptionMinute();
  const [option, setOption] = useState<ScenarioOption | null>(null);
  const { state, run } = useScenarioRun(source);
  useEffect(() => {
    let alive = true;
    source.options(pivot.pivot_id).then((opts) => {
      const on = opts.filter((o) => o.enabled);
      const rank = (o: ScenarioOption) => (STRIKING.indexOf(o.type) + STRIKING.length + 1) % (STRIKING.length + 1);
      const o = (side ? forYourTeam(on, side) : [...on].sort((a, b) => rank(a) - rank(b)))[0];
      if (!alive || !o) return;
      setOption(o);
      run({ pivot_id: pivot.pivot_id, type: o.type, n_runs: 200, ...(Object.keys(o.params).length ? { params: o.params } : {}) });
    }, () => {});
    return () => {
      alive = false;
    };
  }, [source, pivot.pivot_id, side]);
  if (!option || state.phase === "failed" || state.phase === "idle") return null;
  const change = optionLabel(option, t, undefined, minuteOf(option));
  return (
    <section className="wi-feature is-an" aria-labelledby="wi-feature-hd" aria-live="polite">
      <h2 id="wi-feature-hd" tabIndex={-1}>{scoreDashes(t("wi.feature", { change }))}</h2>
      {state.phase === "done" ? (
        <>
          <WhatIfAnswer scenario={state.scenario} change={change} minute={minuteOf(option)}
            pressLower={/lower/i.test(option.label)} teams={teams} compact />
          <p className="muted wi-feature-more">{t("wi.an.featureMore")}</p>
        </>
      ) : (
        <RunProgress scenario={state.phase === "running" ? state.scenario : null} />
      )}
    </section>
  );
}
