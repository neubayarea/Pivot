import { useState } from "react";
import Card from "../components/Card";
import EventFeed from "../components/EventFeed";
import Kicker from "../components/Kicker";
import MatchStats from "../components/MatchStats";
import MomentumChart from "../components/MomentumChart";
import PivotList from "../components/PivotList";
import Playback from "../components/Playback";
import WhyItTurned from "../components/WhyItTurned";
import { useMatch } from "../data/match";

// S1 · Live board. Layout follows "05 S1" in docs/design/matchday-programme.html.
export default function LiveBoard() {
  const { match, teams, metrics, pivots } = useMatch();
  const [evidence, setEvidence] = useState<ReadonlySet<string>>(new Set());
  const latest = pivots.find((p) => p.status === "confirmed") ?? null;
  const minute = Math.floor(match.clock / 60);

  const toggle = (id: string) =>
    setEvidence((s) => {
      const next = new Set(s);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  return (
    <>
      <div className="headline">
        {latest ? (
          <div className="latest" key={latest.pivot_id}>
            <Kicker>Latest pivot · {latest.minute}′</Kicker>
            <span className="x">{latest.narrative?.headline}</span>
          </div>
        ) : (
          <div className="latest">
            <Kicker>Kick-off</Kicker>
            <span className="x">Watching for the first pivot</span>
          </div>
        )}
        <span className="sp" />
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
            <MomentumChart
              metrics={metrics}
              pivots={pivots}
              homeLabel={teams.home.short_name}
              awayLabel={teams.away.short_name}
            />
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
