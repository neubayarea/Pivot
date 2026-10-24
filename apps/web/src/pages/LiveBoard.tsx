import { useState } from "react";
import { Link } from "react-router-dom";
import Card from "../components/Card";
import EventFeed from "../components/EventFeed";
import Kicker from "../components/Kicker";
import MatchStats from "../components/MatchStats";
import MomentumChart from "../components/MomentumChart";
import PitchBoard from "../components/PitchBoard";
import PivotList, { pivotHeadline } from "../components/PivotList";
import StartDemoButton from "../components/StartDemoButton";
import WhyItTurned from "../components/WhyItTurned";
import { useMatch } from "../data/match";
import { useT } from "../i18n";

// S1 · Live board. Layout follows "05 S1" in docs/design/matchday-programme.html.
export default function LiveBoard() {
  const { match, teams, metrics, pivots, playback } = useMatch();
  const t = useT();
  const [evidence, setEvidence] = useState<ReadonlySet<string>>(new Set());
  const latest = pivots.find((p) => p.status === "confirmed" || p.status === "degraded") ?? null;
  const minute = Math.floor(match.clock / 60);
  const scheduled = match.status === "scheduled";
  // On the live feed a finished match leaves nothing in progress; the fixture has its own Restart.
  const over = match.status === "finished" && !playback;

  const toggle = (id: string) =>
    setEvidence((s) => {
      const next = new Set(s);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  return (
    <>
      {latest?.status === "degraded" && (
        <div className="banner warn" role="status">
          {t("banner.degraded")}
        </div>
      )}
      <div className="headline">
        {latest ? (
          <div className="latest" key={latest.pivot_id}>
            <Kicker>{t("board.latest", { minute: latest.minute })}</Kicker>
            <span className="x">{pivotHeadline(latest, teams, t)}</span>
          </div>
        ) : scheduled ? (
          <div className="latest">
            <Kicker>{t("board.kickoffPending")}</Kicker>
            <span className="x">{t("board.versus", { home: teams.home.short_name, away: teams.away.short_name })}</span>
          </div>
        ) : (
          <div className="latest">
            <Kicker>{t("board.kickoff")}</Kicker>
            <span className="x">{t("board.watching")}</span>
          </div>
        )}
        <span className="sp" />
        {latest && (
          <Link to={`/whatif/${latest.pivot_id}`} className="btn" aria-label={`${t("detail.whatIf")} ${t("board.latest", { minute: latest.minute })}`}>
            {t("detail.whatIf")}
          </Link>
        )}
        {over && <StartDemoButton matchId={match.match_id}>{t("demo.startShort")}</StartDemoButton>}
      </div>
      <div className="grid1">
        <div className="stack">
          <Card
            title={t("board.momentum")}
            note={
              <>
                <span style={{ color: "var(--pv-home)" }}>■</span> {teams.home.name} &nbsp;
                <span style={{ color: "var(--pv-away)" }}>■</span> {teams.away.name}
              </>
            }
          >
            {scheduled ? (
              <div className="empty-box">
                {t("board.kickoffPending")} · <StartDemoButton matchId={match.match_id}>{t("demo.startMatch")}</StartDemoButton>
              </div>
            ) : metrics.length ? (
              <MomentumChart
                metrics={metrics}
                pivots={pivots}
                homeLabel={teams.home.short_name}
                awayLabel={teams.away.short_name}
              />
            ) : (
              <div className="empty-box muted">{t("board.momentumEmpty")}</div>
            )}
          </Card>
          {!scheduled && <PitchBoard key={match.match_id} />}
          <div className="lower">
            <WhyItTurned pivot={latest} selected={evidence} onToggle={toggle} />
            <Card title={t("board.events")} note={t("board.autoScroll")}>
              <EventFeed highlight={evidence} />
            </Card>
          </div>
        </div>
        <div className="stack">
          <Card title={t("board.pivots")} note={t("board.pivotsNote", { n: pivots.length })}>
            <PivotList activeId={latest?.pivot_id ?? null} />
          </Card>
          <Card title={t("board.stats")} note={`0′–${minute}′`}>
            <MatchStats />
          </Card>
        </div>
      </div>
    </>
  );
}
