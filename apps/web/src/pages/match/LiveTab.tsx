// 赛中 · Live (Ax59): what used to sit folded in "More details" (Ax41), now a tab of its own. The
// pitch with the replay on top and the match stats beside it, the events under the pitch and the
// line-ups under the stats. A pivot the checker signs off while the viewer watches pops up as an
// alert with a link to its explanation on the post-match tab.
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
  const q = new URLSearchParams(tabSearch(search, "post"));
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

export function LiveTab({ moments, evidence }: { moments: Pivot[]; evidence: ReadonlySet<string> }) {
  const { match, playback } = useMatch();
  const t = useT();
  const { at } = useClock();
  const scheduled = match.status === "scheduled";
  // A stored match that is not being replayed: offer the replay, which moves everything on this tab.
  const over = match.status === "finished" && !playback;
  // C11: the team stats and the pictures follow the replay or the live clock; a stored match shows all of it.
  const upTo = over ? null : match.clock;
  const report = useTeamStats(scheduled ? null : match.match_id, upTo);
  // C12: the ♥ team's summary and the ★ player's spotlight lead for a fan, follow the numbers for an analyst.
  const { fan } = usePersona();
  const mine = !scheduled && (
    <>
      <YourTeamSummary report={report.data} upTo={upTo} />
      <PlayerSpotlight upTo={upTo} />
    </>
  );
  return (
    <>
      {(scheduled || over) && (
        <div className="live-start">
          <p className="muted">{t(scheduled ? "board.kickoffPending" : "live.replayHint")}</p>
          <StartDemoButton matchId={match.match_id}>{t(scheduled ? "demo.startMatch" : "demo.startShort")}</StartDemoButton>
        </div>
      )}
      {fan && mine}
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
      {!fan && mine}
      {!scheduled && (
        <>
          <section className="live-sec" aria-labelledby="live-pics-hd">
            <header className="live-hd">
              <h2 id="live-pics-hd">{t("pics.title")}</h2>
              {!over && <p className="muted">{t("pics.note")}</p>}
            </header>
            <div className="card"><MatchPictures key={match.match_id} upTo={upTo} /></div>
          </section>
          <section className="live-sec" aria-labelledby="live-stats-hd">
            <header className="live-hd">
              <h2 id="live-stats-hd">{t("ts.title")}</h2>
              <p className="muted">{t("ts.note")}</p>
            </header>
            <div className="card"><TeamStats state={report} /></div>
          </section>
        </>
      )}
      <PivotAlert moments={moments} />
    </>
  );
}
