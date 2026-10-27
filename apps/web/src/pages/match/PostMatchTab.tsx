// 赛后 · Post-match (Ax59, C11 Ax64): the analysis, read top to bottom as the story of the match.
// The pivots lead (one line each, the explanation opening under the line picked), then the
// momentum line with the goals on it, the key moments, set pieces and shots, what-if, and the
// AI's work log across the bottom. Styles in styles/post.css.
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import KeyMoments, { KeyLegend, keyId, keyWhat } from "../../components/KeyMoments";
import Kicker from "../../components/Kicker";
import MomentumChart from "../../components/MomentumChart";
import { MomentCards, OpenMoment, WhatIfInline } from "../../components/Moments";
import PlayerCard from "../../components/PlayerCard";
import SetPiecesAndShots from "../../components/SetPieces";
import StartDemoButton from "../../components/StartDemoButton";
import { useClock } from "../../data/clock";
import { keyMoments, matchPhase } from "../../data/keyMoments";
import { useMatch } from "../../data/match";
import { useT } from "../../i18n";
import "../../styles/post.css";

/** One section of the analysis, with its heading and a line on what it shows; the pivots lead. */
function Section({ title, note, children, id, lead = false }: { title: string; note?: ReactNode; children: ReactNode; id: string; lead?: boolean }) {
  return (
    <section className={`post-sec${lead ? " lead-sec" : ""}`} aria-labelledby={`${id}-hd`} id={id}>
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
  const { minute } = useClock();
  const scheduled = match.status === "scheduled";
  const finished = match.status === "finished";
  // On the live feed a finished match leaves nothing in progress; the fixture has its own Restart.
  const over = finished && !playback;
  const phase = matchPhase(match.status, events);
  const score = { home: teams.home.name, away: teams.away.name, score: `${match.score.home}–${match.score.away}` };
  const keys = keyMoments(events, finished);
  // What-if runs on one pivot at a time: the one open above, or the one picked here.
  const [wiFor, setWiFor] = useState<string | null>(null);
  const whatIf = moments.find((p) => p.pivot_id === (wiFor ?? open?.pivot_id)) ?? moments[0] ?? null;
  const n = open ? moments.indexOf(open) + 1 : 0;

  if (scheduled) {
    return (
      <div className="empty-box">
        {t("board.kickoffPending")} <StartDemoButton matchId={match.match_id}>{t("demo.startMatch")}</StartDemoButton>
      </div>
    );
  }

  return (
    <div className="post">
      <div className="lead">
        <Kicker>
          {moments.length
            ? t(finished ? "moments.kickerDone" : "moments.kickerLive", score)
            : t("board.phaseScore", { phase: t(finished ? "status.finished" : phase === "halfTime" ? "board.halfTime" : "board.kickoff"), ...score })}
        </Kicker>
        <h1>
          {moments.length
            ? t(finished ? "moments.title" : "moments.titleLive", { n: moments.length })
            : t(finished ? "board.noSwing" : "board.watching")}
        </h1>
        {over && <StartDemoButton matchId={match.match_id}>{t("demo.startShort")}</StartDemoButton>}
      </div>

      <Section lead id="post-pivots" title={t("post.pivots")} note={moments.length ? t("post.pivotsNote") : undefined}>
        {moments.length ? (
          <MomentCards pivots={moments} selected={open?.pivot_id ?? null} onPick={onPick}
            open={open && <OpenMoment key={open.pivot_id} pivot={open} n={n} evidence={evidence} onEvidence={onEvidence} />} />
        ) : (
          <p className="muted">{t(finished ? "board.noSwingLede" : "pivots.empty")}</p>
        )}
        {/* The ★ player's numbers so far, whole minutes so a live clock refetches once a minute. */}
        <PlayerCard upTo={finished ? null : Math.floor(match.clock / 60) * 60} numbered={moments.map((p) => p.pivot_id)} onPivot={onPick} />
      </Section>

      <Section id="post-momentum" title={t("board.momentum")}
        note={<span className="kit-key">
          <span className="home">{teams.home.name}</span>
          <span className="away">{teams.away.name}</span>
        </span>}>
        <div className="card post-mom">
          {metrics.length ? (
            <MomentumChart
              metrics={metrics}
              pivots={pivots}
              homeLabel={teams.home.short_name}
              awayLabel={teams.away.short_name}
              numbered={moments.map((p) => p.pivot_id)}
              selected={open?.pivot_id ?? null}
              onPick={onPick}
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
        </div>
      </Section>

      <Section id="post-keys" title={t("keys.title")} note={t("keys.note")}>
        <KeyMoments moments={keys} pivots={moments} windows={(p) => pivotDetail(p.pivot_id)?.window} selected={keySelected} onPick={onKey} heading={false} />
      </Section>

      <Section id="post-set-pieces" title={t("sp.title")}>
        <SetPiecesAndShots key={match.match_id} folded={false} />
      </Section>

      <Section id="post-whatif" title={t("detail.whatIf")} note={t("moments.wiNote")}>
        {whatIf ? (
          <div className="post-wi">
            {moments.length > 1 && (
              <div className="chips" role="group" aria-label={t("post.whatIfFor")}>
                {moments.map((p, i) => (
                  <button key={p.pivot_id} type="button" className="chip" aria-pressed={p.pivot_id === whatIf.pivot_id} onClick={() => setWiFor(p.pivot_id)}>
                    {t("post.whatIfAt", { n: i + 1, minute: minute(p.minute) })}
                  </button>
                ))}
              </div>
            )}
            <WhatIfInline key={whatIf.pivot_id} pivot={whatIf} />
          </div>
        ) : (
          <p className="muted">{t("post.whatIfNone")}</p>
        )}
      </Section>

      <Section id="post-trace" title={t("post.trace")}>
        <div className="card post-trace">
          <p>{t("moments.traceNote")}</p>
          <Link to="/trace" className="btn">{t("top.trace", { n: pivots.length })}</Link>
        </div>
      </Section>
    </div>
  );
}
