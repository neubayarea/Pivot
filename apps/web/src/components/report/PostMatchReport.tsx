// The analyst's post-match report on the Overview (C19, #385), after the xG race: deserved result,
// match phases, game state and shot quality, each with a heading, one sentence the data gives and
// where its numbers come from. The numbers are the API's (/analysis, /shots); none is worked out here.
import { useState } from "react";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { isNum, reached, useAnalysis, type MatchAnalysis } from "../../data/analysis";
import { count, num, or0, pct, share } from "./fmt";
import { useClock } from "../../data/clock";
import { keyMoments } from "../../data/keyMoments";
import { useMatch } from "../../data/match";
import { useT, type MessageKey } from "../../i18n";
import { useShotMap } from "../viz";
import { keyWhat } from "../KeyMoments";
import Deserved, { deservedVerdict } from "./Deserved";
import GameStateTable, { mostDangerous, stateFor } from "./GameStateTable";
import Phases, { METRIC_KEY, bestSpell, type PhaseMetric } from "./Phases";
import ReportSection from "./ReportSection";
import ShotQuality from "./ShotQuality";
import Lanes, { LANES, laneShares } from "./Lanes";
import PlayerContrib, { topContributors } from "./PlayerContrib";
import StyleRadar from "./StyleRadar";
import { usePlayers } from "../../data/persona";
import "../../styles/report.css";

export default function PostMatchReport({ moments, upTo }: { moments: Pivot[]; upTo: number | null }) {
  const { match, teams, events, playerName } = useMatch();
  const t = useT();
  const { minute } = useClock();
  const analysis = useAnalysis(match.match_id, upTo);
  const data = analysis.data;
  const shots = useShotMap(match.match_id, { upTo, stepS: 60 });
  const [metric, setMetric] = useState<PhaseMetric>("xg");
  const players = usePlayers(match.match_id, upTo);
  const names = { home: teams.home.short_name, away: teams.away.short_name };
  const full = { home: teams.home.name, away: teams.away.name };
  const score = { home: match.score.home, away: match.score.away };

  const top = players.data ? topContributors(players.data.players, 1)[0] : undefined;
  const plTake = top?.stats ? t("rp.pl.take", { name: top.name, v: num(or0(top.stats.xg) + or0(top.stats.xa)), xg: num(top.stats.xg), xa: num(top.stats.xa) }) : null;
  const shotsSec = (quality: MatchAnalysis["shot_quality"] | null, takeaway: string | null) => (
    <ReportSection id="rp-shots" title={t("rp.sq.title")} takeaway={takeaway} source={t(quality ? "rp.src.shots" : "rp.src.shotsOnly")} className="wide">
      <ShotQuality shots={shots.data?.shots ?? []} quality={quality} names={names} nameOf={playerName} />
    </ReportSection>
  );
  const playersSec = (wide: boolean) => (
    <ReportSection id="rp-players" title={t("rp.pl.title")} takeaway={plTake} source={t("rp.src.players")} className={wide ? "wide" : ""}>
      {players.data && <PlayerContrib players={players.data.players} short={names} />}
    </ReportSection>
  );

  // Without the analysis (not live yet, or the request failed) only the parts drawn from /shots and
  // /players/stats show, so no number on this page is made up. While it loads, an empty outline holds its place.
  if (!data) {
    return (
      <div className="rp">
        {analysis.loading && <div className="rp-wait" role="status" aria-busy="true" aria-label={t("rp.loading")} />}
        {shotsSec(null, null)}
        {playersSec(true)}
      </div>
    );
  }

  // A live match sends nulls for what it has not reached: blocks still to come are left out, and a
  // takeaway is skipped when its numbers are not there yet.
  const phases = (data.phases ?? []).filter(reached);
  const v = deservedVerdict(data.deserved, score);
  const dsvTake = v && t(v.key, { score: `${score.home}–${score.away}`, team: v.side ? full[v.side] : "", p: share(v.p) });

  const spell = bestSpell(phases, metric);
  const mName = t(`metric.${METRIC_KEY[metric]}.short` as MessageKey);
  const fmt = (x: number | null) => (metric === "xg" ? num(x) : metric === "ppda" ? num(x, 1) : pct(x));
  const phTake = spell && t("rp.ph.take", {
    from: phases[spell.i].from, to: phases[spell.i].to, team: full[spell.side], metric: mName,
    v: fmt(phases[spell.i][spell.side][metric]), w: fmt(phases[spell.i][spell.side === "home" ? "away" : "home"][metric]),
  });
  const keys = keyMoments(events, match.status === "finished");
  const marks = [
    ...keys.filter((k) => k.kind === "goal").map((k) => ({ label: k.event.clock_label, side: k.side, kind: "goal" as const, text: `${k.event.clock_label.replace(/'/g, "′")} ${keyWhat(k, t, playerName, (s) => teams[s].short_name)}` })),
    ...moments.map((p, i) => ({ label: minute(p.minute), side: p.direction, kind: "pivot" as const, n: i + 1, text: `${t("xg.keyTurn")} ${i + 1}, ${minute(p.minute)}′` })),
  ];

  const md = mostDangerous(data.game_state);
  const gsTake = md && t("rp.gs.take", { team: full[md.side], state: t(`rp.gs.when.${stateFor(md.row.state, md.side)}` as MessageKey), v: num(md.row[md.side].xg_per90) });

  const q = data.shot_quality;
  const hq = q?.home?.xg_per_shot, aq = q?.away?.xg_per_shot;
  const better = isNum(hq) && isNum(aq) ? (hq >= aq ? "home" : "away") : null;
  const other = better === "home" ? "away" : "home";
  const sqTake = better && t("rp.sq.take", {
    team: full[better], v: num(q[better].xg_per_shot), w: num(q[other].xg_per_shot), n: count(q[better].big_chances), m: count(q[other].big_chances),
  });

  // C19 B: the lane that made the most xG, the clearest difference in style.
  let lane: { side: "home" | "away"; k: (typeof LANES)[number] } | null = null;
  for (const side of ["home", "away"] as const) {
    for (const k of LANES) {
      const x = data.lanes?.[side]?.[k]?.xg;
      if (isNum(x) && x > 0 && (!lane || x > or0(data.lanes[lane.side][lane.k].xg))) lane = { side, k };
    }
  }
  const lnTake = lane && t("rp.ln.take", { team: full[lane.side], lane: t(`rp.ln.word.${lane.k}` as MessageKey), xg: num(data.lanes[lane.side][lane.k].xg), pct: laneShares(data.lanes[lane.side])[lane.k] });
  const pf = data.profile;
  let gap = -1;
  pf.metrics.forEach((_, i) => {
    const h = pf.home[i], a = pf.away[i];
    if (isNum(h) && isNum(a) && (gap < 0 || Math.abs(h - a) > Math.abs(or0(pf.home[gap]) - or0(pf.away[gap])))) gap = i;
  });
  const ahead = gap >= 0 && or0(pf.home[gap]) >= or0(pf.away[gap]) ? "home" : "away";
  const pfTake = gap >= 0 ? t("rp.pf.take", {
    metric: t(`rp.pf.${pf.metrics[gap]}` as MessageKey), team: full[ahead],
    v: count(pf[ahead][gap]), w: count(pf[ahead === "home" ? "away" : "home"][gap]),
  }) : null;

  return (
    <div className="rp">
      <ReportSection id="rp-deserved" title={t("rp.dsv.title")} takeaway={dsvTake} source={t("rp.src.deserved", { n: data.deserved.n_sims.toLocaleString() })}>
        <Deserved d={data.deserved} names={names} score={score} />
      </ReportSection>
      {data.game_state?.length > 0 && (
        <ReportSection id="rp-state" title={t("rp.gs.title")} takeaway={gsTake} source={t("rp.src.state")}>
          <GameStateTable rows={data.game_state} names={names} />
        </ReportSection>
      )}
      {phases.length > 0 && (
        <ReportSection id="rp-phases" title={t("rp.ph.title")} takeaway={phTake} source={t("rp.src.phases")} className="wide">
          <Phases phases={phases} names={names} marks={marks} onMetric={setMetric} />
        </ReportSection>
      )}
      {shotsSec(q, sqTake)}
      <ReportSection id="rp-lanes" title={t("rp.ln.title")} takeaway={lnTake} source={t("rp.src.lanes")} className="wide">
        <Lanes lanes={data.lanes} names={full} />
      </ReportSection>
      {playersSec(false)}
      <ReportSection id="rp-profile" title={t("rp.pf.title")} takeaway={pfTake} source={t("rp.src.profile", { n: pf.baseline_matches })}>
        <StyleRadar profile={pf} names={names} />
      </ReportSection>
    </div>
  );
}
