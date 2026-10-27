// 赛后 · Post-match (Ax59, redrawn C11 #288). The momentum line is the hero: the AI's turning
// points sit on it as yellow pins and as one line each straight under it; the open one unfolds
// below with why it turned, the pitch at that moment, and what-if for that same moment. Key
// moments, set pieces and shots, and the AI's work log follow, quieter.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import KeyMoments, { KeyLegend, keyId, keyWhat } from "../../components/KeyMoments";
import MomentumChart from "../../components/MomentumChart";
import { MomentCards, OpenMoment, WhatIfInline } from "../../components/Moments";
import PlayerCard from "../../components/PlayerCard";
import SetPiecesAndShots from "../../components/SetPieces";
import StartDemoButton from "../../components/StartDemoButton";
import { keyMoments, matchPhase } from "../../data/keyMoments";
import { useMatch } from "../../data/match";
import { useT } from "../../i18n";

/** One section of the analysis, with its heading and a line on what it shows. */
function Section({ title, note, children, id, className = "" }: { title: string; note?: ReactNode; children: ReactNode; id: string; className?: string }) {
  return (
    <section className={`post-sec ${className}`.trim()} aria-labelledby={`${id}-hd`} id={id}>
      <header className="sec-hd">
        <h2 id={`${id}-hd`}>{title}</h2>
        {note && <p className="muted">{note}</p>}
      </header>
      {children}
    </section>
  );
}

type Props = {
  moments: Pivot[];
  open: Pivot | null;
  onPick: (id: string) => void;
  evidence: ReadonlySet<string>;
  onEvidence: (id: string) => void;
  keySelected: string | null;
  onKey: (id: string | null) => void;
};

export function PostMatchTab({ moments, open, onPick, evidence, onEvidence, keySelected, onKey }: Props) {
  const { match, teams, metrics, pivots, playback, events, playerName, pivotDetail } = useMatch();
  const t = useT();
  const scheduled = match.status === "scheduled";
  const finished = match.status === "finished";
  // On the live feed a finished match leaves nothing in progress; the fixture has its own Restart.
  const over = finished && !playback;
  const phase = matchPhase(match.status, events);
  const keys = keyMoments(events, finished);
  const n = open ? moments.indexOf(open) + 1 : 0;

  if (scheduled) {
    return (
      <div className="empty-box">
        {t("board.kickoffPending")} <StartDemoButton matchId={match.match_id}>{t("demo.startMatch")}</StartDemoButton>
      </div>
    );
  }

  return (
    <>
      <header className="post-lead">
        <div>
          <h1>
            {moments.length
              ? t(finished ? "moments.title" : "moments.titleLive", { n: moments.length })
              : t(finished ? "board.noSwing" : "board.watching")}
          </h1>
          <p className="lede">
            {moments.length
              ? t("moments.lede")
              : t(finished ? "board.noSwingLede" : "board.phaseScore", {
                phase: t(phase === "halfTime" ? "board.halfTime" : "board.kickoff"),
                home: teams.home.name, away: teams.away.name, score: `${match.score.home}–${match.score.away}`,
              })}
          </p>
        </div>
        {over && <StartDemoButton matchId={match.match_id}>{t("demo.startShort")}</StartDemoButton>}
      </header>

      <section className="turns" aria-labelledby="post-momentum-hd" id="post-momentum">
        <header className="turns-hd">
          <h2 id="post-momentum-hd">{t("board.momentum")}</h2>
          <ul className="team-key" aria-hidden="true">
            <li className="home">{teams.home.name}</li>
            <li className="away">{teams.away.name}</li>
          </ul>
        </header>
        {metrics.length ? (
          <MomentumChart
            metrics={metrics}
            pivots={pivots}
            homeLabel={teams.home.short_name}
            awayLabel={teams.away.short_name}
            numbered={moments.map((p) => p.pivot_id)}
            selected={open?.pivot_id ?? null}
            onPick={onPick}
            windowAt={open ? pivotDetail(open.pivot_id)?.window ?? null : null}
            keys={keys.map((k) => ({
              id: keyId(k), t: k.event.t, kind: k.kind, side: k.side,
              label: t("keys.open", { minute: k.event.clock_label.replace(/'$/, ""), what: keyWhat(k, t, playerName, (s) => teams[s].short_name) }),
            }))}
            keySelected={keySelected}
            onKey={(id) => onKey(id === keySelected ? null : id)}
          />
        ) : (
          <div className="empty-box muted">{t("board.momentumEmpty")}</div>
        )}
        {metrics.length > 0 && keys.length > 0 && <KeyLegend kinds={new Set(keys.map((k) => k.kind))} pivots={moments.length > 0} />}
        <div id="post-pivots" aria-label={t("post.pivots")} role="group">
          {moments.length ? (
            <MomentCards pivots={moments} selected={open?.pivot_id ?? null} onPick={onPick} />
          ) : (
            <p className="muted">{t(finished ? "board.noSwingLede" : "pivots.empty")}</p>
          )}
        </div>
      </section>

      {open && (
        <OpenMoment key={open.pivot_id} pivot={open} n={n} evidence={evidence} onEvidence={onEvidence}
          onPrev={n > 1 ? () => onPick(moments[n - 2].pivot_id) : undefined}
          onNext={n < moments.length ? () => onPick(moments[n].pivot_id) : undefined}>
          <WhatIfInline key={open.pivot_id} pivot={open} />
        </OpenMoment>
      )}
      {/* The ★ player's numbers so far, whole minutes so a live clock refetches once a minute. */}
      <PlayerCard upTo={finished ? null : Math.floor(match.clock / 60) * 60} numbered={moments.map((p) => p.pivot_id)} onPivot={onPick} />

      <Section id="post-keys" title={t("keys.title")} note={t("keys.note")}>
        <KeyMoments moments={keys} pivots={moments} windows={(p) => pivotDetail(p.pivot_id)?.window} selected={keySelected} onPick={onKey} heading={false} />
      </Section>

      <Section id="post-set-pieces" title={t("sp.title")}>
        <SetPiecesAndShots key={match.match_id} folded={false} />
      </Section>

      <Section id="post-trace" title={t("post.trace")} className="post-trace">
        <p className="muted">{t("moments.traceNote")}</p>
        <Link to="/trace" className="btn">{t("top.trace", { n: pivots.length })}</Link>
      </Section>
    </>
  );
}
