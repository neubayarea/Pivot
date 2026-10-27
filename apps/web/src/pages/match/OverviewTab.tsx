// 赛后 · Post-match (Ax59, redrawn C11 Ax64 after momomojun's prototype on b/C-ui-overhaul, #288).
// One hero: the momentum line with the AI's turning points pinned on it and one line each under it.
// The open one (the first when none is picked) is the only raised panel: why it turned, the pitch
// at that moment and what-if for that same moment. Key moments, set pieces and shots and the AI's
// work log follow, quieter. Styles in styles/post.css.
// 概况 · Overview (Ax69, #316 #322): the tab that opens after the match, and it changes with who is
// watching (data/persona.ts). A fan gets their ♥ team's match, the ★ player and the story of the
// match in cards; an analyst gets the momentum line with the turning points and the open one. Both
// get the key moments and the five core team stats, and the AI's work log is a link at the bottom.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import KeyMoments, { KeyLegend, keyId, keyWhat } from "../../components/KeyMoments";
import MomentumChart from "../../components/MomentumChart";
import { MomentCards, OpenMoment, WhatIfInline } from "../../components/Moments";
import MatchStory from "../../components/MatchStory";
import PlayerSpotlight from "../../components/PlayerSpotlight";
import SetPiecesAndShots from "../../components/SetPieces";
import StartDemoButton from "../../components/StartDemoButton";
import TeamStats, { useTeamStats } from "../../components/TeamStats";
import YourTeamSummary from "../../components/YourTeamSummary";
import { keyMoments, matchPhase } from "../../data/keyMoments";
import { useMatch } from "../../data/match";
import { FAN5, usePersona } from "../../data/persona";
import { useT } from "../../i18n";
import "../../styles/post.css";

/** One section of the analysis, with its heading and a line on what it shows; the pivots lead. */
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

const CORE = new Set<string>(FAN5);

export function OverviewTab({ moments, open, onPick, evidence, onEvidence, keySelected, onKey }: Props) {
  const { match, teams, metrics, pivots, playback, events, playerName, pivotDetail } = useMatch();
  const t = useT();
  const scheduled = match.status === "scheduled";
  const finished = match.status === "finished";
  // On the live feed a finished match leaves nothing in progress; the fixture has its own Restart.
  const over = finished && !playback;
  const phase = matchPhase(match.status, events);
  const keys = keyMoments(events, finished);
  // With none picked the first one is open, so the page lands on an explanation (C11 prototype).
  const shown = open ?? moments[0] ?? null;
  const n = shown ? moments.indexOf(shown) + 1 : 0;
  // Picking the one already open keeps it open; the prototype has no folded state.
  const pick = (id: string) => id !== shown?.pivot_id && onPick(id);
  const { fan, side } = usePersona();
  // The team stats follow the replay or the live clock, whole minutes, like the live tab's.
  const upTo = finished ? null : Math.floor(match.clock / 60) * 60;
  const report = useTeamStats(scheduled ? null : match.match_id, upTo);

  if (scheduled) {
    return (
      <div className="empty-box">
        {t("board.kickoffPending")} <StartDemoButton matchId={match.match_id}>{t("demo.startMatch")}</StartDemoButton>
      </div>
    );
  }

  return (
    <div className={`post ${fan ? "fan" : "analyst"}`} data-audience={fan ? "fan" : "analyst"}>
      <header className="post-lead">
        <div>
          <h1>
            {moments.length
              ? t(finished ? "moments.title" : "moments.titleLive", { n: moments.length })
              : t(finished ? "board.noSwing" : "board.watching")}
          </h1>
          <p className="lede">
            {moments.length
              ? t(fan ? (side ? "ov.ledeFanTeam" : "ov.ledeFan") : "moments.lede")
              : t(finished ? "board.noSwingLede" : "board.phaseScore", {
                phase: t(phase === "halfTime" ? "board.halfTime" : "board.kickoff"),
                home: teams.home.name, away: teams.away.name, score: `${match.score.home}–${match.score.away}`,
              })}
          </p>
        </div>
        {over && <StartDemoButton matchId={match.match_id}>{t("demo.startShort")}</StartDemoButton>}
      </header>

      {/* The ♥ team's match leads for everyone who picked one. */}
      <YourTeamSummary report={report.data} upTo={upTo} />
      {/* A fan has no open turning point here: the spotlight links to its own page. */}
      {fan && <PlayerSpotlight upTo={upTo} />}
      {fan && (
        <Section id="post-story" title={t("story.title")} note={t("story.note")}>
          <MatchStory />
        </Section>
      )}

      {!fan && <section className="turns" aria-labelledby="post-momentum-hd" id="post-momentum">
        <header className="turns-hd">
          <h2 id="post-momentum-hd">{t("board.momentum")}</h2>
          <span className="kit-key" aria-hidden="true">
            <span className="home">{teams.home.name}</span>
            <span className="away">{teams.away.name}</span>
          </span>
        </header>
        {metrics.length ? (
          <MomentumChart
            metrics={metrics}
            pivots={pivots}
            homeLabel={teams.home.short_name}
            awayLabel={teams.away.short_name}
            numbered={moments.map((p) => p.pivot_id)}
            selected={shown?.pivot_id ?? null}
            onPick={pick}
            windowAt={shown ? pivotDetail(shown.pivot_id)?.window ?? null : null}
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
        <div id="post-pivots" role="group" aria-label={t("post.pivots")}>
          {moments.length ? (
            <MomentCards pivots={moments} selected={shown?.pivot_id ?? null} onPick={pick} />
          ) : (
            <p className="muted">{t(finished ? "board.noSwingLede" : "pivots.empty")}</p>
          )}
        </div>
      </section>}

      {!fan && shown && (
        <OpenMoment key={shown.pivot_id} pivot={shown} n={n} evidence={evidence} onEvidence={onEvidence}
          onPrev={n > 1 ? () => onPick(moments[n - 2].pivot_id) : undefined}
          onNext={n < moments.length ? () => onPick(moments[n].pivot_id) : undefined}>
          <WhatIfInline key={shown.pivot_id} pivot={shown} />
        </OpenMoment>
      )}
      {/* The ★ player's spotlight (C12) after the turning points for an analyst, whole minutes so a live clock refetches once a minute. */}
      {!fan && <PlayerSpotlight upTo={upTo} onPivot={pick} />}

      <Section id="post-keys" title={t("keys.title")} note={t("keys.note")}>
        <KeyMoments moments={keys} pivots={moments} windows={(p) => pivotDetail(p.pivot_id)?.window} selected={keySelected} onPick={onKey} heading={false} />
      </Section>

      <Section id="post-core" title={t("ov.core")} note={t(fan ? "ov.coreNoteFan" : "ov.coreNote")}>
        <div className="card"><TeamStats state={report} only={CORE} /></div>
      </Section>

      {!fan && (
        <Section id="post-set-pieces" title={t("sp.title")}>
          <SetPiecesAndShots key={match.match_id} folded={false} />
        </Section>
      )}

      <Section id="post-trace" title={t("post.trace")} className="post-trace">
        <p>{t("moments.traceNote")}</p>
        <Link to="/trace" className="btn">{t("top.trace", { n: pivots.length })}</Link>
      </Section>
    </div>
  );
}
