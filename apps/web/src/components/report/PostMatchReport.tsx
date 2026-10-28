// The analyst's report (C19 #385, rebalanced C20 #391): parts the Overview and the Stats tab each pick
// from. The Overview keeps the short read (deserved result, key players); the Stats tab is the deep
// one (phases, game state, shot quality, lanes, style). Each part has a heading, one sentence the data
// gives, the chart and where its numbers come from. The numbers are the API's (/analysis, /shots,
// /players/stats); none is worked out here.
//
// While the match is on, or a finished match is replayed short of full time (`upTo` set), the words
// are "so far": "Live numbers · up to 67′", "by the chances so far", present-tense takeaways, and the
// 15-minute blocks still to come are greyed "not started".
import { useState, type ReactElement } from "react";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { isNum, reached, useAnalysis } from "../../data/analysis";
import { useClock } from "../../data/clock";
import { keyMoments } from "../../data/keyMoments";
import { useMatch } from "../../data/match";
import { usePlayers } from "../../data/persona";
import { useT, type MessageKey } from "../../i18n";
import { keyWhat } from "../KeyMoments";
import { useShotMap } from "../viz";
import Deserved, { deservedVerdict } from "./Deserved";
import GameStateTable, { mostDangerous, stateFor } from "./GameStateTable";
import Lanes, { LANES, laneShares } from "./Lanes";
import Phases, { METRIC_KEY, bestSpell, type PhaseMetric } from "./Phases";
import PlayerContrib, { topContributors } from "./PlayerContrib";
import ReportSection from "./ReportSection";
import SetPiecesAndShots from "../SetPieces";
import ShotQuality from "./ShotQuality";
import StyleRadar from "./StyleRadar";
import { count, num, or0, pct, share } from "./fmt";
import "../../styles/report.css";

export type ReportPart = "deserved" | "phases" | "state" | "shots" | "setPieces" | "lanes" | "profile" | "players";

type Props = {
  parts: readonly ReportPart[];
  moments: Pivot[];
  /** Seconds the numbers run to; null for a finished match seen in full. */
  upTo: number | null;
  /** Key players shown (8 on the Stats tab, 5 on the Overview). */
  players?: number;
  /** h2 on a page of its own (the Stats tab, for its "on this page" row), h3 inside a section. */
  level?: 2 | 3;
  /** Every part full width, one under the other (the Stats tab), not two to a row. */
  stack?: boolean;
};

/** The take key for a finished match, or its "so far" twin while the match is on. */
const tk = (live: boolean, key: string) => (live ? `${key}Live` : key) as MessageKey;

export default function PostMatchReport({ parts, moments, upTo, players: nPlayers = 8, level = 3, stack = false }: Props) {
  const { match, teams, events, playerName } = useMatch();
  const t = useT();
  const { minute } = useClock();
  const live = upTo !== null;
  const analysis = useAnalysis(match.match_id, upTo);
  const data = analysis.data;
  const shots = useShotMap(parts.includes("shots") ? match.match_id : null, { upTo, stepS: 60 });
  const [metric, setMetric] = useState<PhaseMetric>("xg");
  const players = usePlayers(parts.includes("players") ? match.match_id : null, upTo);
  const names = { home: teams.home.short_name, away: teams.away.short_name };
  const full = { home: teams.home.name, away: teams.away.name };
  const score = { home: match.score.home, away: match.score.away };
  const sec = { level, live };

  const top = players.data ? topContributors(players.data.players, 1)[0] : undefined;
  const plTake = top?.stats ? t(tk(live, "rp.pl.take"), { name: top.name, v: num(or0(top.stats.xg) + or0(top.stats.xa)), xg: num(top.stats.xg), xa: num(top.stats.xa) }) : null;

  const out: Partial<Record<ReportPart, ReactElement | null>> = {};
  out.players = (
    <ReportSection key="players" id="rp-players" title={t("rp.pl.title")} takeaway={plTake} source={t("rp.src.players")} {...sec}
      className={parts.length === 1 || !data ? "wide" : ""}>
      {players.data && <PlayerContrib players={players.data.players} short={names} n={nPlayers} />}
    </ReportSection>
  );
  const q = data?.shot_quality ?? null;
  const hq = q?.home?.xg_per_shot, aq = q?.away?.xg_per_shot;
  const better = isNum(hq) && isNum(aq) ? (hq >= aq ? "home" : "away") : null;
  const other = better === "home" ? "away" : "home";
  const sqTake = q && better && t(tk(live, "rp.sq.take"), {
    team: full[better], v: num(q[better].xg_per_shot), w: num(q[other].xg_per_shot), n: count(q[better].big_chances), m: count(q[other].big_chances),
  });
  out.shots = (
    <ReportSection key="shots" id="rp-shots" title={t("rp.sq.title")} takeaway={sqTake} source={t(q ? "rp.src.shots" : "rp.src.shotsOnly")} className="wide" {...sec}>
      <ShotQuality shots={shots.data?.shots ?? []} quality={q} names={names} nameOf={playerName} />
    </ReportSection>
  );
  // Ax89 (#410): the set pieces and shot clips, moved here from the analyst's Overview. Drawn from the
  // events and frames, so it shows with or without /analysis.
  out.setPieces = (
    <ReportSection key="setPieces" id="rp-set-pieces" title={t("rp.sp.title")} source={t("rp.src.setPieces")} className="wide" {...sec}>
      <SetPiecesAndShots key={match.match_id} folded={false} />
    </ReportSection>
  );

  if (data) {
    // A live match sends nulls for what it has not reached: a takeaway is skipped when its numbers are not there yet.
    const v = deservedVerdict(data.deserved, score);
    const dsvTake = v && t(live ? (v.side ? "rp.dsv.liveWin" : "rp.dsv.liveDraw") : v.key, {
      score: `${score.home}–${score.away}`, team: v.side ? full[v.side] : "", p: share(v.p),
    });
    out.deserved = (
      <ReportSection key="deserved" id="rp-deserved" title={t(live ? "rp.dsv.titleLive" : "rp.dsv.title")} takeaway={dsvTake}
        note={live ? t("rp.dsv.liveNote") : null} source={t("rp.src.deserved", { n: data.deserved.n_sims.toLocaleString() })} {...sec}>
        <Deserved d={data.deserved} names={names} score={score} live={live} />
      </ReportSection>
    );

    const phases = data.phases ?? [];
    const spell = bestSpell(phases, metric);
    const mName = t(`metric.${METRIC_KEY[metric]}.short` as MessageKey);
    const fmt = (x: number | null) => (metric === "xg" ? num(x) : metric === "ppda" ? num(x, 1) : pct(x));
    const phTake = spell && t(tk(live, "rp.ph.take"), {
      from: phases[spell.i].from, to: phases[spell.i].to, team: full[spell.side], metric: mName,
      v: fmt(phases[spell.i][spell.side][metric]), w: fmt(phases[spell.i][spell.side === "home" ? "away" : "home"][metric]),
    });
    const keys = keyMoments(events, match.status === "finished");
    const marks = [
      ...keys.filter((k) => k.kind === "goal").map((k) => ({ label: k.event.clock_label, side: k.side, kind: "goal" as const, text: `${k.event.clock_label.replace(/'/g, "′")} ${keyWhat(k, t, playerName, (s) => teams[s].short_name)}` })),
      ...moments.map((p, i) => ({ label: minute(p.minute), side: p.direction, kind: "pivot" as const, n: i + 1, text: `${t("xg.keyTurn")} ${i + 1}, ${minute(p.minute)}′` })),
    ];
    out.phases = phases.some(reached) ? (
      <ReportSection key="phases" id="rp-phases" title={t("rp.ph.title")} takeaway={phTake} source={t("rp.src.phases")} className="wide" {...sec}>
        <Phases phases={phases} names={names} marks={marks} onMetric={setMetric} />
      </ReportSection>
    ) : null;

    const md = mostDangerous(data.game_state ?? []);
    const gsTake = md && t(tk(live, "rp.gs.take"), { team: full[md.side], state: t(`rp.gs.when.${stateFor(md.row.state, md.side)}` as MessageKey), v: num(md.row[md.side].xg_per90) });
    out.state = data.game_state?.length ? (
      <ReportSection key="state" id="rp-state" title={t("rp.gs.title")} takeaway={gsTake} source={t("rp.src.state")} {...sec}>
        <GameStateTable rows={data.game_state} names={names} />
      </ReportSection>
    ) : null;

    let lane: { side: "home" | "away"; k: (typeof LANES)[number] } | null = null;
    for (const side of ["home", "away"] as const) {
      for (const k of LANES) {
        const x = data.lanes?.[side]?.[k]?.xg;
        if (isNum(x) && x > 0 && (!lane || x > or0(data.lanes[lane.side][lane.k].xg))) lane = { side, k };
      }
    }
    const lnTake = lane && t(tk(live, "rp.ln.take"), { team: full[lane.side], lane: t(`rp.ln.word.${lane.k}` as MessageKey), xg: num(data.lanes[lane.side][lane.k].xg), pct: laneShares(data.lanes[lane.side])[lane.k] });
    out.lanes = data.lanes ? (
      <ReportSection key="lanes" id="rp-lanes" title={t("rp.ln.title")} takeaway={lnTake} source={t("rp.src.lanes")} className="wide" {...sec}>
        <Lanes lanes={data.lanes} names={full} />
      </ReportSection>
    ) : null;

    const pf = data.profile;
    let gap = -1;
    pf?.metrics.forEach((_, i) => {
      const h = pf.home[i], a = pf.away[i];
      if (isNum(h) && isNum(a) && (gap < 0 || Math.abs(h - a) > Math.abs(or0(pf.home[gap]) - or0(pf.away[gap])))) gap = i;
    });
    const ahead = pf && gap >= 0 && or0(pf.home[gap]) >= or0(pf.away[gap]) ? "home" : "away";
    const pfTake = pf && gap >= 0 ? t(tk(live, "rp.pf.take"), {
      metric: t(`rp.pf.${pf.metrics[gap]}` as MessageKey), team: full[ahead],
      v: count(pf[ahead][gap]), w: count(pf[ahead === "home" ? "away" : "home"][gap]),
    }) : null;
    out.profile = pf ? (
      <ReportSection key="profile" id="rp-profile" title={t("rp.pf.title")} takeaway={pfTake} source={t("rp.src.profile", { n: pf.baseline_matches })} {...sec}
        className={parts.includes("players") ? "" : "wide"}>
        <StyleRadar profile={pf} names={names} />
      </ReportSection>
    ) : null;
  }

  const shown = parts.map((p) => out[p]).filter(Boolean);
  // Without the analysis (not live yet, or the request failed) only the parts drawn from /shots and
  // /players/stats show, so no number on this page is made up. While it loads, an empty outline holds its place.
  return (
    <div className={`rp${stack ? " stack" : ""}`}>
      {!data && analysis.loading && <div className="rp-wait" role="status" aria-busy="true" aria-label={t("rp.loading")} />}
      {shown}
    </div>
  );
}

/** The heading over the report: "Post-match analysis" for a finished match seen in full, else "Live numbers · up to 67′". */
export function useReportTitle(upTo: number | null): string {
  const t = useT();
  const { at } = useClock();
  return upTo === null ? t("rp.title") : t("rp.titleLive", { minute: at(upTo) });
}
