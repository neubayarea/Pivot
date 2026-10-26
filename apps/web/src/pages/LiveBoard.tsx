import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import Card from "../components/Card";
import EventFeed from "../components/EventFeed";
import KeyMoments, { KeyLegend, keyId, keyWhat } from "../components/KeyMoments";
import Kicker from "../components/Kicker";
import MatchStats from "../components/MatchStats";
import MomentumChart from "../components/MomentumChart";
import { MomentCards, OpenMoment } from "../components/Moments";
import PitchBoard from "../components/PitchBoard";
import StartDemoButton from "../components/StartDemoButton";
import { useClock } from "../data/clock";
import { keyMoments, matchPhase } from "../data/keyMoments";
import { useMatch } from "../data/match";
import { useT } from "../i18n";

// S1 · Match board (Ax32). One line saying what the page is for, the momentum line with the
// numbered moments, one card per moment, the picked one opened, everything else folded below.
// Layout follows docs/design/redesign-mockup.html. Ax38: the key moments (goals, red cards, ...)
// sit under the pivots, and lead the page when a finished match never turned.
export default function LiveBoard() {
  const { match, teams, metrics, pivots, playback, events, playerName, pivotDetail } = useMatch();
  const t = useT();
  const { at } = useClock();
  const [evidence, setEvidence] = useState<ReadonlySet<string>>(new Set());
  // Pivots still being checked get a mark on the line but no card yet; the checker's rejects get neither.
  const moments = pivots.filter((p) => p.status === "confirmed" || p.status === "degraded").sort((a, b) => a.minute - b.minute);
  const [picked, setPicked] = useState<string | null>(null);
  const open = moments.find((p) => p.pivot_id === picked) ?? moments[0] ?? null;
  const n = open ? moments.indexOf(open) + 1 : 0;
  const scheduled = match.status === "scheduled";
  // On the live feed a finished match leaves nothing in progress; the fixture has its own Restart.
  const over = match.status === "finished" && !playback;
  const finished = match.status === "finished";
  const phase = matchPhase(match.status, events);
  const score = { home: teams.home.name, away: teams.away.name, score: `${match.score.home}–${match.score.away}` };
  const keys = useMemo(() => keyMoments(events, finished), [events, finished]);
  const [key, setKey] = useState<string | null>(null);
  const pickKey = (id: string) => {
    setKey(id);
    const k = keys.find((k) => keyId(k) === id);
    // The replay goes to that second and stops there, so the pitch (under More details) shows it.
    if (k && playback) {
      playback.setPlaying(false);
      playback.seek(k.event.t);
    }
  };

  // Another match or another moment: the evidence picked for the last one no longer applies.
  useEffect(() => {
    setPicked(null);
    setKey(null);
  }, [match.match_id]);
  useEffect(() => setEvidence(new Set()), [open?.pivot_id]);

  const pick = (id: string) => setPicked(id);
  const toggle = (id: string) =>
    setEvidence((s) => {
      const next = new Set(s);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  return (
    <>
      <div className="lead">
        {scheduled ? (
          <>
            <Kicker>{t("board.kickoffPending")}</Kicker>
            <h1>{t("board.versus", { home: teams.home.name, away: teams.away.name })}</h1>
          </>
        ) : moments.length ? (
          <>
            <Kicker>{t(match.status === "finished" ? "moments.kickerDone" : "moments.kickerLive", { home: teams.home.name, away: teams.away.name, score: `${match.score.home}–${match.score.away}` })}</Kicker>
            <h1>{t(match.status === "finished" ? "moments.title" : "moments.titleLive", { n: moments.length })}</h1>
            <p className="lede">{t("moments.lede")}</p>
          </>
        ) : finished ? (
          <>
            <Kicker>{t("board.phaseScore", { phase: t("status.finished"), ...score })}</Kicker>
            <h1>{t("board.noSwing")}</h1>
            <p className="lede">{t("board.noSwingLede")}</p>
          </>
        ) : (
          <>
            <Kicker>{t("board.phaseScore", { phase: t(phase === "halfTime" ? "board.halfTime" : "board.kickoff"), ...score })}</Kicker>
            <h1>{t("board.watching")}</h1>
          </>
        )}
        {over && <StartDemoButton matchId={match.match_id}>{t("demo.startShort")}</StartDemoButton>}
      </div>
      <div className="board">
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
              numbered={moments.map((p) => p.pivot_id)}
              selected={open?.pivot_id ?? null}
              onPick={pick}
              keys={keys.map((k) => ({
                id: keyId(k), t: k.event.t, kind: k.kind, side: k.side,
                label: t("keys.open", { minute: k.event.clock_label.replace(/'$/, ""), what: keyWhat(k, t, playerName, (s) => teams[s].short_name) }),
              }))}
              keySelected={key}
              onKey={pickKey}
            />
          ) : (
            <div className="empty-box muted">{t("board.momentumEmpty")}</div>
          )}
          {!scheduled && metrics.length > 0 && keys.length > 0 && (
            <KeyLegend kinds={new Set(keys.map((k) => k.kind))} pivots={moments.length > 0} />
          )}
        </Card>
        {!moments.length && !finished && <p className="muted">{t("pivots.empty")}</p>}
        {moments.length > 0 && <MomentCards pivots={moments} selected={open?.pivot_id ?? null} onPick={pick} />}
        {open && <OpenMoment key={open.pivot_id} pivot={open} n={n} evidence={evidence} onEvidence={toggle} />}
        {!scheduled && (
          <KeyMoments moments={keys} pivots={moments} windows={(p) => pivotDetail(p.pivot_id)?.window} selected={key} onPick={pickKey} />
        )}
        <details className="more">
          <summary>
            {t("moments.more")} <small>{t("moments.moreNote")}</small>
          </summary>
          <div className="more-bd">
            {!scheduled && <PitchBoard key={match.match_id} />}
            <Card title={t("board.events")} note={t("board.autoScroll")}>
              <EventFeed highlight={evidence} />
            </Card>
            <Card title={t("board.stats")} note={`0′–${at(match.clock)}′`}>
              <MatchStats />
            </Card>
            <Card title={t("trace.kicker")}>
              <p className="muted">{t("moments.traceNote")}</p>
              <Link to="/trace" className="btn">{t("top.trace", { n: pivots.length })}</Link>
            </Card>
          </div>
        </details>
      </div>
    </>
  );
}
