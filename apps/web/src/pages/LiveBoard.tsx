import { useState } from "react";
import Card from "../components/Card";
import EventFeed from "../components/EventFeed";
import Kicker from "../components/Kicker";
import MatchStats from "../components/MatchStats";
import MomentumChart from "../components/MomentumChart";
import PivotList, { pivotHeadline } from "../components/PivotList";
import Playback from "../components/Playback";
import StartDemoButton from "../components/StartDemoButton";
import WhyItTurned from "../components/WhyItTurned";
import { useMatch } from "../data/match";

// S1 · Live board. Layout follows "05 S1" in docs/design/matchday-programme.html.
export default function LiveBoard() {
  const { match, teams, metrics, pivots, playback } = useMatch();
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
          AI explanations delayed. Showing automatic summaries.
        </div>
      )}
      <div className="headline">
        {latest ? (
          <div className="latest" key={latest.pivot_id}>
            <Kicker>Latest pivot · {latest.minute}′</Kicker>
            <span className="x">{pivotHeadline(latest, teams)}</span>
          </div>
        ) : scheduled ? (
          <div className="latest">
            <Kicker>Kick-off pending</Kicker>
            <span className="x">{teams.home.short_name} v {teams.away.short_name}</span>
          </div>
        ) : (
          <div className="latest">
            <Kicker>Kick-off</Kicker>
            <span className="x">Watching for the first pivot</span>
          </div>
        )}
        <span className="sp" />
        {over && <StartDemoButton>Start demo</StartDemoButton>}
        <Playback />
      </div>
      <div className="grid1">
        <div className="stack">
          <Card
            title="Momentum"
            note={
              <>
                <span style={{ color: "var(--pv-home)" }}>■</span> {teams.home.name} &nbsp;
                <span style={{ color: "var(--pv-away)" }}>■</span> {teams.away.name}
              </>
            }
          >
            {scheduled ? (
              <div className="empty-box">
                Kick-off pending · <StartDemoButton matchId={match.match_id}>Start match</StartDemoButton>
              </div>
            ) : metrics.length ? (
              <MomentumChart
                metrics={metrics}
                pivots={pivots}
                homeLabel={teams.home.short_name}
                awayLabel={teams.away.short_name}
              />
            ) : (
              <div className="empty-box muted">The momentum line starts after the first minute of play.</div>
            )}
          </Card>
          <div className="lower">
            <WhyItTurned pivot={latest} selected={evidence} onToggle={toggle} />
            <Card title="Events" note="auto-scroll">
              <EventFeed highlight={evidence} />
            </Card>
          </div>
        </div>
        <div className="stack">
          <Card title="Pivots" note={`${pivots.length} this match`}>
            <PivotList activeId={latest?.pivot_id ?? null} />
          </Card>
          <Card title="Match stats" note={`0′–${minute}′`}>
            <MatchStats />
          </Card>
        </div>
      </div>
    </>
  );
}
