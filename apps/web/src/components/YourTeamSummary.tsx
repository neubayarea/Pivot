// "How your team did" (C12, #311): shown once the viewer picks a ♥ team. The result, the three
// stats where the team was furthest ahead and the three where it was furthest behind (from the 23
// MET of #279, PPDA counted the right way round), its best-rated player (#226), and one template
// sentence. No AI: the same numbers the explanations cite. Fans see the plain stat names.
import type { CSSProperties } from "react";
import type { TeamStatsReport } from "@pivot/contracts";
import { useMatch } from "../data/match";
import { bestPlayer, other, result, strengthsAndWeaknesses, teamLine, usePersona, usePlayers, type StatEdge } from "../data/persona";
import { isMessageKey, usePrefs, type T } from "../i18n";
import FollowButton from "./FollowButton";
import { Placeholder } from "./Skeleton";
import { statText, useTeamStats } from "./TeamStats";

/** The stat's name in the viewer's words: plain for fans where there is a plain one. */
export function statLabel(metric: string, fan: boolean, t: T): string {
  const k = fan && isMessageKey(`ts.fan.${metric}`) ? `ts.fan.${metric}` : `ts.m.${metric}`;
  return isMessageKey(k) ? t(k as never) : metric;
}

function Edges({ title, edges, report, fan, t }: { title: string; edges: StatEdge[]; report: TeamStatsReport; fan: boolean; t: T }) {
  const info = (m: string) => report.metrics.find((x) => x.metric === m)!;
  return (
    <div className="you-col">
      <h3>{title}</h3>
      <ul>
        {edges.map((e) => (
          <li key={e.metric}>
            <span>{statLabel(e.metric, fan, t)}</span>
            <b className="num">{statText(e.mine, info(e.metric))}</b>
            <span className="num muted">{statText(e.theirs, info(e.metric))}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Pass the stats report when the page already has one (the live tab does); otherwise it fetches its own.
 * `upTo`: elapsed seconds for a replay or a live match, null for the whole match. Renders nothing without a ♥ team.
 */
export default function YourTeamSummary({ report, upTo = null }: { report?: TeamStatsReport | null; upTo?: number | null }) {
  const { match, teams } = useMatch();
  const { prefs, t } = usePrefs();
  const { side, fan } = usePersona();
  const own = useTeamStats(side && report === undefined ? match.match_id : null, upTo);
  const players = usePlayers(side ? match.match_id : null, upTo);
  if (!side) return null;
  const stats = report ?? own.data;
  const team = teams[side].name;
  // Fans only hear about stats that have a plain name (no PPDA, no field tilt), and never an xG number.
  const plain = fan ? new Set((stats?.metrics ?? []).map((m) => m.metric).filter((m) => m !== "xg" && isMessageKey(`ts.fan.${m}`))) : undefined;
  const { strengths, weaknesses } = strengthsAndWeaknesses(stats, side, 3, plain);
  const best = bestPlayer(players.data?.players ?? [], side);
  const line = teamLine(t as never, prefs.language, {
    team, score: match.score, side,
    strengths: strengths.map((e) => statLabel(e.metric, fan, t)),
    weaknesses: weaknesses.map((e) => statLabel(e.metric, fan, t)),
    best: best?.stats ? { name: best.name, rating: best.stats.rating } : null,
  });
  return (
    <section className={`you ${result(match.score, side)}`} aria-labelledby="you-hd"
      style={{ "--tc": `var(--pv-${side})`, "--oc": `var(--pv-${other(side)})` } as CSSProperties}>
      <header className="you-hd">
        <h2 id="you-hd">{t("you.title", { team })}</h2>
        <span className="you-score num" aria-hidden="true">{match.score[side]}–{match.score[other(side)]}</span>
      </header>
      {stats ? <p className="you-line">{line}</p> : <Placeholder label={t("you.loading")} lines={4} />}
      {stats && (
        <div className="you-cols">
          {strengths.length > 0 && <Edges title={t("you.strengths")} edges={strengths} report={stats} fan={fan} t={t} />}
          {weaknesses.length > 0 && <Edges title={t("you.weaknesses")} edges={weaknesses} report={stats} fan={fan} t={t} />}
          {best?.stats && (
            <div className="you-col you-best">
              <h3>{t("you.best")}</h3>
              <p><span className="you-shirt num">{best.shirt_number}</span> <b>{best.name}</b></p>
              <p className="you-rating num">{best.stats.rating.toFixed(1)}</p>
              <FollowButton playerId={best.player_id} name={best.name} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
