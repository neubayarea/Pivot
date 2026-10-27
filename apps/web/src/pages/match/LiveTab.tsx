// 回放 / 直播 · Replay (Live while the match is played) and 数据 · Stats (Ax59, split by content
// in C13 #316). Replay: the pitch with the replay on top, the key stats beside it and the events
// under it; a pivot the checker signs off while the viewer watches pops up as an alert with a link
// to its explanation on the overview. Stats: the ♥ team's summary and the ★ player's spotlight
// (C12), the grouped team stats and the match pictures.
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import Card from "../../components/Card";
import EventFeed from "../../components/EventFeed";
import MatchPictures from "../../components/MatchPictures";
import MatchStats from "../../components/MatchStats";
import PitchBoard from "../../components/PitchBoard";
import PlayerSpotlight from "../../components/PlayerSpotlight";
import { pivotHeadline } from "../../components/PivotList";
import StartDemoButton from "../../components/StartDemoButton";
import TeamStats, { useTeamStats } from "../../components/TeamStats";
import YourTeamSummary from "../../components/YourTeamSummary";
import { useClock } from "../../data/clock";
import { useMatch } from "../../data/match";
import { usePersona } from "../../data/persona";
import { tabSearch } from "../../data/tab";
import { useT } from "../../i18n";

// An alert stays up this long unless the viewer closes it or opens it.
const ALERT_MS = 15_000;

/** The pivot that just appeared, if any: one that was not on the board the last time it changed. */
function PivotAlert({ moments }: { moments: Pivot[] }) {
  const { teams } = useMatch();
  const t = useT();
  const { minute } = useClock();
  const { search } = useLocation();
  const seen = useRef<Set<string> | null>(null);
  const [shown, setShown] = useState<Pivot | null>(null);
  const ids = moments.map((p) => p.pivot_id).join();

  useEffect(() => {
    // The pivots already there when the tab opens are not news.
    if (seen.current) {
      const fresh = moments.filter((p) => !seen.current!.has(p.pivot_id)).at(-1);
      if (fresh) setShown(fresh);
    }
    seen.current = new Set(moments.map((p) => p.pivot_id));
  }, [ids]);
  useEffect(() => {
    if (!shown) return;
    const id = setTimeout(() => setShown(null), ALERT_MS);
    return () => clearTimeout(id);
  }, [shown]);

  if (!shown) return null;
  const q = new URLSearchParams(tabSearch(search, "overview"));
  q.set("pivot", shown.pivot_id);
  return (
    <aside className={`pv-alert to-${shown.direction}`} role="status" aria-live="polite">
      <span className="pv-alert-k">{t("live.alert", { minute: minute(shown.minute) })}</span>
      <b className="pv-alert-hd">{pivotHeadline(shown, teams, t)}</b>
      <span className="pv-alert-ft">
        <Link to={{ search: `?${q}` }} className="more-link">{t("live.alertOpen")}</Link>
        <button type="button" className="btn ghost" onClick={() => setShown(null)}>{t("live.alertClose")}</button>
      </span>
    </aside>
  );
}

/** A stored match that is not being replayed shows everything; a replay or a live match shows up to the clock. */
function useUpTo() {
  const { match, playback } = useMatch();
  const over = match.status === "finished" && !playback;
  return { over, upTo: over ? null : match.clock };
}

/** Replay (Live while the match is played, C13 #316): the pitch, the five key stats and the events. */
export function LiveTab({ moments, evidence }: { moments: Pivot[]; evidence: ReadonlySet<string> }) {
  const { match } = useMatch();
  const t = useT();
  const { at, minute } = useClock();
  const scheduled = match.status === "scheduled";
  const { over, upTo } = useUpTo();
  const report = useTeamStats(scheduled ? null : match.match_id, upTo);
  return (
    <>
      {scheduled && (
        <div className="live-start">
          <p className="muted">{t("board.kickoffPending")}</p>
          <StartDemoButton matchId={match.match_id}>{t("demo.startMatch")}</StartDemoButton>
        </div>
      )}
      {/* C13 UX: a finished match offers the replay from kick-off or straight from the first turning point. */}
      {over && (
        <div className="live-start replay-start">
          <p>{t("live.replayHint")}</p>
          <span className="replay-go">
            <StartDemoButton matchId={match.match_id}>{t("live.replayStart")}</StartDemoButton>
            {moments[0] && (
              <a className="btn" href={`/?match=${encodeURIComponent(match.match_id)}&from=${Math.max(0, moments[0].minute - 1)}&tab=replay`}>
                {t("live.replayFrom", { n: 1, minute: minute(moments[0].minute) })}
              </a>
            )}
          </span>
        </div>
      )}
      <div className="more-bd live-bd">
        {/* Ax41: one screen. Pitch and stats on top, events and line-ups under them. */}
        {!scheduled && <PitchBoard key={match.match_id} />}
        <Card title={t("board.stats")} note={`0′–${at(match.clock)}′`} className="more-stats">
          <MatchStats report={report.data} />
        </Card>
        <Card title={t("board.events")} note={t("board.autoScroll")} className="more-events">
          <EventFeed highlight={evidence} />
        </Card>
      </div>
      <PivotAlert moments={moments} />
    </>
  );
}

/**
 * Stats (C13 #316): the 23 team stats grouped (five plain ones for a fan), then the shot map,
 * heatmaps, pass network and average positions. The ♥ team's summary and the ★ player's spotlight
 * (C12) lead for a fan and follow the numbers for an analyst.
 */
export function StatsTab() {
  const { match } = useMatch();
  const t = useT();
  const scheduled = match.status === "scheduled";
  const { over, upTo } = useUpTo();
  const report = useTeamStats(scheduled ? null : match.match_id, upTo);
  const { fan } = usePersona();
  if (scheduled) return <div className="empty-box">{t("board.kickoffPending")}</div>;
  const mine = (
    <>
      <YourTeamSummary report={report.data} upTo={upTo} />
      <PlayerSpotlight upTo={upTo} />
    </>
  );
  return (
    <>
      {fan && mine}
      <section className="live-sec" aria-labelledby="live-stats-hd">
        <header className="live-hd">
          <h2 id="live-stats-hd">{t("ts.title")}</h2>
          <p className="muted">{t("ts.note")}</p>
        </header>
        <div className="card"><TeamStats state={report} /></div>
      </section>
      <section className="live-sec" aria-labelledby="live-pics-hd">
        <header className="live-hd">
          <h2 id="live-pics-hd">{t("pics.title")}</h2>
          {!over && <p className="muted">{t("pics.note")}</p>}
        </header>
        <div className="card"><MatchPictures key={match.match_id} upTo={upTo} /></div>
      </section>
      {!fan && mine}
    </>
  );
}
