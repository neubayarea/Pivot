// The analyst's post-match report on the Overview (C19, #385), after the xG race: deserved result,
// match phases, game state and shot quality, each with a heading, one sentence the data gives and
// where its numbers come from. The numbers are the API's (/analysis, /shots); none is worked out here.
import { useState } from "react";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { useAnalysis } from "../../data/analysis";
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
  const { data, sample } = useAnalysis(match.match_id, upTo);
  const shots = useShotMap(match.match_id, { upTo, stepS: 60 });
  const [metric, setMetric] = useState<PhaseMetric>("xg");
  const players = usePlayers(match.match_id, upTo);
  if (!data) return null;
  const names = { home: teams.home.short_name, away: teams.away.short_name };
  const full = { home: teams.home.name, away: teams.away.name };
  const score = { home: match.score.home, away: match.score.away };

  const v = deservedVerdict(data.deserved, score);
  const dsvTake = t(v.key, { score: `${score.home}–${score.away}`, team: v.side ? full[v.side] : "", p: `${Math.round(v.p * 100)}%` });

  const spell = bestSpell(data.phases, metric);
  const mName = t(`metric.${METRIC_KEY[metric]}.short` as MessageKey);
  const fmt = (x: number | null) => (x === null ? "–" : metric === "xg" ? x.toFixed(2) : metric === "ppda" ? x.toFixed(1) : `${Math.round(x)}%`);
  const phTake = spell && t("rp.ph.take", {
    from: data.phases[spell.i].from, to: data.phases[spell.i].to, team: full[spell.side], metric: mName,
    v: fmt(data.phases[spell.i][spell.side][metric]), w: fmt(data.phases[spell.i][spell.side === "home" ? "away" : "home"][metric]),
  });
  const keys = keyMoments(events, match.status === "finished");
  const marks = [
    ...keys.filter((k) => k.kind === "goal").map((k) => ({ label: k.event.clock_label, side: k.side, kind: "goal" as const, text: `${k.event.clock_label.replace(/'/g, "′")} ${keyWhat(k, t, playerName, (s) => teams[s].short_name)}` })),
    ...moments.map((p, i) => ({ label: minute(p.minute), side: p.direction, kind: "pivot" as const, n: i + 1, text: `${t("xg.keyTurn")} ${i + 1}, ${minute(p.minute)}′` })),
  ];

  const md = mostDangerous(data.game_state);
  const gsTake = md && t("rp.gs.take", { team: full[md.side], state: t(`rp.gs.when.${stateFor(md.row.state, md.side)}` as MessageKey), v: md.row[md.side].xg_per90.toFixed(2) });

  const q = data.shot_quality;
  const better = q.home.xg_per_shot >= q.away.xg_per_shot ? "home" : "away";
  const other = better === "home" ? "away" : "home";
  const sqTake = t("rp.sq.take", { team: full[better], v: q[better].xg_per_shot.toFixed(2), w: q[other].xg_per_shot.toFixed(2), n: q[better].big_chances, m: q[other].big_chances });

  // C19 B: the lane that made the most xG, the clearest difference in style, the top contributor.
  let lane: { side: "home" | "away"; k: (typeof LANES)[number] } | null = null;
  for (const side of ["home", "away"] as const) {
    for (const k of LANES) if (!lane || data.lanes[side][k].xg > data.lanes[lane.side][lane.k].xg) lane = { side, k };
  }
  const lnTake = lane && t("rp.ln.take", { team: full[lane.side], lane: t(`rp.ln.word.${lane.k}` as MessageKey), xg: data.lanes[lane.side][lane.k].xg.toFixed(2), pct: laneShares(data.lanes[lane.side])[lane.k] });
  const pf = data.profile;
  let gap = -1;
  pf.metrics.forEach((_, i) => { if (gap < 0 || Math.abs(pf.home[i] - pf.away[i]) > Math.abs(pf.home[gap] - pf.away[gap])) gap = i; });
  const ahead = gap >= 0 && pf.home[gap] >= pf.away[gap] ? "home" : "away";
  const pfTake = gap >= 0 ? t("rp.pf.take", {
    metric: t(`rp.pf.${pf.metrics[gap]}` as MessageKey), team: full[ahead],
    v: Math.round(pf[ahead][gap]), w: Math.round(pf[ahead === "home" ? "away" : "home"][gap]),
  }) : null;
  const top = players.data ? topContributors(players.data.players, 1)[0] : undefined;
  const plTake = top?.stats ? t("rp.pl.take", { name: top.name, v: (top.stats.xg + top.stats.xa).toFixed(2), xg: top.stats.xg.toFixed(2), xa: top.stats.xa.toFixed(2) }) : null;

  return (
    <div className="rp" style={{ ["--rp-cols" as string]: 2 }}>
      <ReportSection id="rp-deserved" title={t("rp.dsv.title")} takeaway={dsvTake} source={t("rp.src.deserved", { n: data.deserved.n_sims.toLocaleString() })} sample={sample}>
        <Deserved d={data.deserved} names={names} score={score} />
      </ReportSection>
      <ReportSection id="rp-state" title={t("rp.gs.title")} takeaway={gsTake} source={t("rp.src.state")} sample={sample}>
        <GameStateTable rows={data.game_state} names={names} />
      </ReportSection>
      <ReportSection id="rp-phases" title={t("rp.ph.title")} takeaway={phTake} source={t("rp.src.phases")} sample={sample} className="wide">
        <Phases phases={data.phases} names={names} marks={marks} onMetric={setMetric} />
      </ReportSection>
      <ReportSection id="rp-shots" title={t("rp.sq.title")} takeaway={sqTake} source={t("rp.src.shots")} sample={sample} className="wide">
        <ShotQuality shots={shots.data?.shots ?? []} quality={q} names={names} nameOf={playerName} />
      </ReportSection>
      <ReportSection id="rp-lanes" title={t("rp.ln.title")} takeaway={lnTake} source={t("rp.src.lanes")} sample={sample} className="wide">
        <Lanes lanes={data.lanes} names={full} />
      </ReportSection>
      <ReportSection id="rp-players" title={t("rp.pl.title")} takeaway={plTake} source={t("rp.src.players")}>
        {players.data && <PlayerContrib players={players.data.players} short={names} />}
      </ReportSection>
      <ReportSection id="rp-profile" title={t("rp.pf.title")} takeaway={pfTake} source={t("rp.src.profile", { n: pf.baseline_matches })} sample={sample}>
        <StyleRadar profile={pf} names={names} />
      </ReportSection>
    </div>
  );
}
