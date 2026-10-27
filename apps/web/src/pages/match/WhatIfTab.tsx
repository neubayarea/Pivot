// 假如 · What-if (C13 #316): the lab gets a tab of its own. Pick a turning point here, then a change
// in the lab; the first turning point is open when the link names none (`&pivot=`).
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { useClock } from "../../data/clock";
import { useT } from "../../i18n";
import { Lab, useScenarioSource } from "../WhatIfLab";

export function WhatIfTab({ moments, open, onPick }: { moments: Pivot[]; open: Pivot | null; onPick: (id: string) => void }) {
  const t = useT();
  const { minute } = useClock();
  const source = useScenarioSource();
  const pivot = open ?? moments[0] ?? null;
  if (!pivot) return <p className="muted">{t("post.whatIfNone")}</p>;
  return (
    <>
      {moments.length > 1 && (
        <div className="chips wi-pivots" role="group" aria-label={t("post.whatIfFor")}>
          {moments.map((p, i) => (
            <button key={p.pivot_id} type="button" className="chip" aria-pressed={p.pivot_id === pivot.pivot_id} onClick={() => onPick(p.pivot_id)}>
              {t("post.whatIfAt", { n: i + 1, minute: minute(p.minute) })}
            </button>
          ))}
        </div>
      )}
      <div className="wi-tab">
        <Lab key={pivot.pivot_id} pivotId={pivot.pivot_id} source={source} />
      </div>
    </>
  );
}
