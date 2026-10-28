// 回放 / 直播 · Replay (Live while the match is played) and 数据 · Stats (Ax59, split by content
// in C13 #316). Replay: the pitch with the replay on top, the key stats beside it and the events
// under it; a pivot the checker signs off while the viewer watches pops up as an alert with a link
// to its explanation on the overview. Stats: the ♥ team's summary and the ★ player's spotlight
// (C12), the grouped team stats and the match pictures.
import { useEffect, useRef, useState, type ComponentType, type CSSProperties } from "react";
import { Link, useLocation } from "react-router-dom";
import type { Pivot1 as Pivot, TeamStatsReport } from "@pivot/contracts";
import Card from "../../components/Card";
import EventFeed from "../../components/EventFeed";
import MatchPictures from "../../components/MatchPictures";
import MatchStats from "../../components/MatchStats";
import PitchBoard from "../../components/PitchBoard";
import PlayerSpotlight from "../../components/PlayerSpotlight";
import PlayerTable from "../../components/PlayerTable";
import LiveCentre from "../../components/live/LiveCentre";
import FanPhases from "../../components/report/FanPhases";
import PageNav from "../../components/report/PageNav";
import PostMatchReport, { useReportTitle } from "../../components/report/PostMatchReport";
import ReportBoundary from "../../components/report/ReportBoundary";
import { pivotHeadline } from "../../components/PivotList";
import StartDemoButton from "../../components/StartDemoButton";
import TeamStats, { useTeamStats } from "../../components/TeamStats";
import YourTeamSummary from "../../components/YourTeamSummary";
import { useClock } from "../../data/clock";
import { useMatch } from "../../data/match";
import { usePersona } from "../../data/persona";
import { tabSearch } from "../../data/tab";
import { useT, type MessageKey } from "../../i18n";
import "../../styles/live-layout.css";

// The UI sub-task gives PitchBoard a `simple` prop (no shape / tactics table, no "vs 5 min before",
// no key hints) for fans; until it lands the prop is ignored.
const Pitch = PitchBoard as unknown as ComponentType<{ simple?: boolean }>;

const FAN_BARS = [["possession_pct", "possession"], ["shots", "shots"], ["shots_on_target", "sot"]] as const;

/** A fan's three numbers under the pitch, each a bar split between the two teams (C21, #401). */
function FanBars({ report }: { report: TeamStatsReport | null | undefined }) {
  const { teams } = useMatch();
  const t = useT();
  const scope = report?.scopes[0];
  if (!scope) return null;
  return (
    <ul className="live-bars" aria-label={t("live.fan.bars")}>
      {FAN_BARS.map(([k, label]) => {
        const h = scope.home[k] ?? null, a = scope.away[k] ?? null;
        if (h === null || a === null) return null;
        const total = h + a;
        const share = total > 0 ? (100 * h) / total : 50;
        const show = (v: number) => (k === "possession_pct" ? `${Math.round(v)}%` : String(Math.round(v)));
        return (
          <li key={k}>
            <span className="live-bar-k">{t(`live.fan.bar.${label}` as MessageKey)}</span>
            <span className="live-bar-v num home" aria-label={`${teams.home.name} ${show(h)}`}>{show(h)}</span>
            <span className="live-bar" aria-hidden="true" style={{ "--share": `${share}%` } as CSSProperties}><i /></span>
            <span className="live-bar-v num away" aria-label={`${teams.away.name} ${show(a)}`}>{show(a)}</span>
          </li>
        );
      })}
    </ul>
  );
}

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

/**
 * Replay (Live while the match is played, C13 #316). C21 (#401): the two viewers get two layouts.
 *  - Analyst: the pitch (about 62 %) with the live centre beside it, sticky (the last ten minutes'
 *    numbers, the deserved result so far, the shot card); the events and the match stats under them.
 *  - Fan: a simpler pitch with, beside it, who is on top now, the momentum line and the big moments
 *    only; under them three big bars, and the full stats folded away.
 */
export function LiveTab({ moments, evidence }: { moments: Pivot[]; evidence: ReadonlySet<string> }) {
  const { match } = useMatch();
  const t = useT();
  const { at, minute } = useClock();
  const { fan } = usePersona();
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
      {fan ? (
        <div className="live-lay fan">
          {!scheduled && <Pitch key={match.match_id} simple />}
          <div className="live-side">
            <LiveCentre moments={moments} upTo={upTo} />
            <Card title={t("live.fan.moments")} note={t("board.autoScroll")} className="more-events live-big">
              <EventFeed highlight={evidence} />
            </Card>
          </div>
          <section className="live-below card" aria-label={t("board.stats")}>
            <FanBars report={report.data} />
            <details className="live-more">
              <summary>{t("live.fan.more")}</summary>
              <MatchStats report={report.data} />
            </details>
          </section>
        </div>
      ) : (
        <div className="live-lay an">
          {!scheduled && <PitchBoard key={match.match_id} />}
          <div className="live-side">
            <LiveCentre moments={moments} upTo={upTo} />
          </div>
          <Card title={t("board.events")} note={t("board.autoScroll")} className="more-events">
            <EventFeed highlight={evidence} />
          </Card>
          <Card title={t("board.stats")} note={`0′–${at(match.clock)}′`} className="more-stats">
            <MatchStats report={report.data} />
          </Card>
        </div>
      )}
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
  const { match, pivots } = useMatch();
  const t = useT();
  const root = useRef<HTMLDivElement>(null);
  const scheduled = match.status === "scheduled";
  const { over, upTo } = useUpTo();
  const report = useTeamStats(scheduled ? null : match.match_id, upTo);
  const { fan } = usePersona();
  const reportTitle = useReportTitle(upTo);
  if (scheduled) return <div className="empty-box">{t("board.kickoffPending")}</div>;
  const moments = pivots.filter((p) => p.status === "confirmed" || p.status === "degraded").sort((a, b) => a.minute - b.minute);
  const mine = (
    <>
      <YourTeamSummary report={report.data} upTo={upTo} />
      <PlayerSpotlight upTo={upTo} />
    </>
  );
  // C20 (#391): the Stats tab is the deep read. An analyst gets the team stats, then the report's
  // phases, game state, shot quality, set pieces (Ax89), lanes and style, the pictures and the player table, with an
  // "on this page" row; a fan gets the key numbers, who was on top when, and the pictures.
  return (
    <div ref={root} className="stats-page">
      <PageNav root={root} />
      {fan && mine}
      <section className="live-sec" aria-labelledby="live-stats-hd">
        <header className="live-hd">
          <h2 id="live-stats-hd">{t("ts.title")}</h2>
          <p className="muted">{t("ts.note")}</p>
        </header>
        <div className="card"><TeamStats state={report} /></div>
      </section>
      {fan ? (
        <ReportBoundary resetKey={`${match.match_id}:${upTo}`}><FanPhases upTo={upTo} /></ReportBoundary>
      ) : (
        <div className="live-sec stats-report">
          <p className="rp-kicker">{reportTitle}</p>
          <ReportBoundary resetKey={`${match.match_id}:${upTo}`}>
            <PostMatchReport parts={["phases", "state", "shots", "setPieces", "lanes", "profile"]} level={2} stack moments={moments} upTo={upTo} />
          </ReportBoundary>
        </div>
      )}
      <section className="live-sec" aria-labelledby="live-pics-hd">
        <header className="live-hd">
          <h2 id="live-pics-hd">{t("pics.title")}</h2>
          {!over && <p className="muted">{t("pics.note")}</p>}
        </header>
        <div className="card"><MatchPictures key={match.match_id} upTo={upTo} /></div>
      </section>
      {!fan && (
        <section className="live-sec" aria-labelledby="live-pt-hd">
          <header className="live-hd"><h2 id="live-pt-hd">{t("pt.title")}</h2></header>
          <div className="card"><PlayerTable upTo={upTo} /></div>
        </section>
      )}
      {!fan && mine}
    </div>
  );
}
