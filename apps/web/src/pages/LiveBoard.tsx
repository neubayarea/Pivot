import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import MatchTabs from "../components/MatchTabs";
import { useMatch } from "../data/match";
import { useTab } from "../data/tab";
import { onAir } from "../data/view";
import { useT } from "../i18n";
import { LineupsTab } from "./match/LineupsTab";
import { LiveTab, StatsTab } from "./match/LiveTab";
import { PostMatchTab } from "./match/PostMatchTab";
import { PreviewTab } from "./match/PreviewTab";
import { WhatIfTab } from "./match/WhatIfTab";

// S1 · Match board (Ax32) under the sticky match header, in six tabs by content (C13 #316, after
// FotMob, Sofascore and the Premier League site): overview, what-if, replay, stats, line-ups,
// preview. Each tab is its own link (`?tab=`, data/tab.ts), and the open pivot is in the link too
// (`&pivot=pv-…`) so a pivot alert on the replay can open its explanation on the overview.
export default function LiveBoard() {
  const view = useMatch();
  const { match, pivots } = view;
  const tab = useTab();
  const t = useT();
  const tabName = t(tab === "replay" && onAir(view) ? "tabs.live" : `tabs.${tab}`);
  const [params, setParams] = useSearchParams();
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
        {/* C13 QA: one h1 per page. The overview and the what-if lab have their own; the other tabs are named by the tab. */}
        {tab !== "overview" && tab !== "whatif" && <h1 className="sr-only">{tabName}</h1>}
        {tab === "overview" && (
          <PostMatchTab moments={moments} open={open} onPick={pick} evidence={evidence} onEvidence={toggle}
            keySelected={key} onKey={setKey} />
        )}
        {tab === "whatif" && <WhatIfTab moments={moments} open={open} onPick={pick} />}
        {tab === "replay" && <LiveTab moments={moments} evidence={evidence} />}
        {tab === "stats" && <StatsTab />}
        {tab === "lineups" && <LineupsTab />}
        {tab === "preview" && <PreviewTab />}
      </div>
    </>
  );
}
