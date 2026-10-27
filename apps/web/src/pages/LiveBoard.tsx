import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import MatchTabs from "../components/MatchTabs";
import { useMatch } from "../data/match";
import { useTab } from "../data/tab";
import { LineupsTab } from "./match/LineupsTab";
import { LiveTab } from "./match/LiveTab";
import { OverviewTab } from "./match/OverviewTab";
import { PreMatchTab } from "./match/PreMatchTab";

// S1 · Match board (Ax32), split Premier League style into before / during / after the match
// (Ax59, #276) under the sticky match header. Each tab is its own link (`?tab=pre|live|post`), the
// live one by default, and the open pivot is in the link too (`&pivot=pv-…`) so a pivot alert on
// the live tab can open its explanation on the post-match tab.
export default function LiveBoard() {
  const { match, pivots } = useMatch();
  const tab = useTab();
  const [params, setParams] = useSearchParams();
  // Ax69: the line-ups tab opens on `?tab=lineups` until the tab shell (#316) gives it a tab of its own.
  const lineups = params.get("tab") === "lineups";
  const [evidence, setEvidence] = useState<ReadonlySet<string>>(new Set());
  // Pivots still being checked get a mark on the line but no card yet; the checker's rejects get neither.
  const moments = pivots.filter((p) => p.status === "confirmed" || p.status === "degraded").sort((a, b) => a.minute - b.minute);
  const open = moments.find((p) => p.pivot_id === params.get("pivot")) ?? null;
  const [key, setKey] = useState<string | null>(null);

  // Another match or another moment: the evidence picked for the last one no longer applies.
  useEffect(() => setKey(null), [match.match_id]);
  useEffect(() => setEvidence(new Set()), [open?.pivot_id]);

  // Picking the open one again folds it away.
  const pick = (id: string) =>
    setParams((q) => {
      if (id === open?.pivot_id) q.delete("pivot");
      else q.set("pivot", id);
      return q;
    }, { replace: true, preventScrollReset: true });
  const toggle = (id: string) =>
    setEvidence((s) => {
      const next = new Set(s);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  return (
    <>
      <MatchTabs tab={tab} />
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="board">
        {lineups && <LineupsTab />}
        {!lineups && tab === "pre" && <PreMatchTab />}
        {!lineups && tab === "live" && <LiveTab moments={moments} evidence={evidence} />}
        {tab === "post" && (
          <OverviewTab moments={moments} open={open} onPick={pick} evidence={evidence} onEvidence={toggle}
            keySelected={key} onKey={setKey} />
        )}
      </div>
    </>
  );
}
