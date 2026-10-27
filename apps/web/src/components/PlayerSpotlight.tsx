// Player spotlight (C12, #311): shown once the viewer follows a ★ player, on the live and the
// post-match tab. Who they are, their rating against the team's average, six numbers picked for
// their position (#226), their own heatmap, their shots and their place in the pass network
// (#287), the turning points they were in and what they did there, and their story before the match.
import { useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { useClock } from "../data/clock";
import { useMatch } from "../data/match";
import { coreStats, roleGroup, teamRating, usePersona, usePlayers, type StatKey } from "../data/persona";
import { usePrefs } from "../i18n";
import { describe } from "./EventFeed";
import FollowButton from "./FollowButton";
import LangTag from "./LangTag";
import { pivotHeadline } from "./PivotList";
import { usePlayerReport } from "./PlayerCard";
import Segmented from "./Segmented";
import { Heatmap, PassNetwork, ShotMap, VizBox, useHeatmaps, usePassNetwork, useShotMap } from "./viz";

type Pic = "heat" | "shots" | "net";

const fmt = (k: StatKey, v: number | null) =>
  v === null ? "–" : k === "pass_accuracy_pct" ? `${Math.round(v)}%` : k === "xg" ? v.toFixed(2) : k === "distance_km" ? v.toFixed(1) : String(Math.round(v));

/** `upTo`: elapsed seconds for a replay or a live match, null for the whole match. Renders nothing with no ★ player. */
export default function PlayerSpotlight({ upTo = null, onPivot }: { upTo?: number | null; onPivot?: (pivotId: string) => void }) {
  const { match, teams, squads, pivots, eventById, playerName, preMatch } = useMatch();
  const { t } = usePrefs();
  const { minute } = useClock();
  const { player, fan } = usePersona();
  const report = usePlayerReport(match.match_id, player, upTo);
  const all = usePlayers(player ? match.match_id : null, upTo);
  const [pic, setPic] = useState<Pic>("heat");
  const opts = { upTo, stepS: 60 };
  const heat = useHeatmaps(player && pic === "heat" ? match.match_id : null, opts);
  const shots = useShotMap(player && pic === "shots" ? match.match_id : null, opts);
  const net = usePassNetwork(player && pic === "net" ? match.match_id : null, opts);
  if (!player) return null;
  if (report === undefined) return <section className="spot"><p className="muted" role="status">{t("spot.loading")}</p></section>;
  if (!report) return null;

  const side = report.team;
  const s = report.stats;
  const avg = teamRating(all.data?.players ?? [], side);
  const names = { home: teams.home.name, away: teams.away.name };
  const ctx = preMatch?.context;
  const news = ctx?.news.filter((n) => n.subject_id === player) ?? [];
  const effects = ctx?.effects.filter((e) => e.subject_id === player) ?? [];
  const ties = ctx?.relationships.filter((r) => r.person_id === player || r.other_id === player) ?? [];

  return (
    <section className="spot" aria-labelledby="spot-hd" style={{ "--tc": `var(--pv-${side})` } as CSSProperties}>
      <div className="spot-who">
        <span className="spot-shirt num" aria-hidden="true">{report.shirt_number}</span>
        <div>
          <p className="spot-k">{t("spot.title")}</p>
          <h2 id="spot-hd">{report.name}</h2>
          <FollowButton playerId={report.player_id} name={report.name} />
          <p className="muted">{teams[side].name}, {fan ? t(`role.${roleGroup(report.role)}`) : report.role}</p>
        </div>
        {s && (
          <div className="spot-rating">
            <b className="num">{s.rating.toFixed(1)}</b>
            {avg !== null && <span className="muted">{t("spot.vsTeam", { n: avg.toFixed(1) })}</span>}
          </div>
        )}
      </div>

      {s ? (
        <dl className="spot-stats">
          {/* Fans get no xG number: top speed in its place. */}
          {coreStats(report.role).map((k) => (fan && k === "xg" ? "top_speed_kmh" : k)).map((k) => (
            <div key={k}><dt>{t(`spot.stat.${k}` as never)}</dt><dd className="num">{fmt(k, s[k] as number | null)}</dd></div>
          ))}
        </dl>
      ) : <p className="muted">{t("spot.noStats")}</p>}

      <div className="spot-bd">
        <div className="spot-pic">
          <Segmented label={t("spot.pics")} value={pic} onChange={setPic} options={[
            { value: "heat", label: t("spot.heat") },
            { value: "shots", label: t("spot.shots") },
            { value: "net", label: t("spot.passing") },
          ]} />
          {pic === "heat" && <VizBox state={heat}>{(d) => <Heatmap data={d} side={side} playerId={player} squads={squads} teamNames={names} />}</VizBox>}
          {pic === "shots" && (
            <VizBox state={shots}>
              {(d) => {
                const mine = d.shots.filter((x) => x.player_id === player);
                return mine.length ? <ShotMap data={{ ...d, shots: mine }} squads={squads} teamNames={names} /> : <p className="muted">{t("spot.noShots")}</p>;
              }}
            </VizBox>
          )}
          {pic === "net" && <VizBox state={net}>{(d) => <PassNetwork data={d} side={side} squads={squads} teamNames={names} focus={player} />}</VizBox>}
        </div>

        <div className="spot-side">
          <h3>{t("spot.pivots")}</h3>
          {report.pivots.length ? (
            <ul className="spot-pivots">
              {report.pivots.map((l) => {
                const p = pivots.find((x) => x.pivot_id === l.pivot_id);
                const did = l.event_ids.map(eventById).filter(Boolean).slice(0, 2).map((e) => describe(e!, playerName, t));
                const head = (
                  <>
                    <b className="num">{minute(l.minute)}′</b> {p ? pivotHeadline(p, teams, t) : ""}
                    {l.in_trigger && <span className="stamp line">{t("spot.setOff")}</span>}
                  </>
                );
                return (
                  <li key={l.pivot_id}>
                    {onPivot ? <button type="button" className="spot-pv" onClick={() => onPivot(l.pivot_id)}>{head}</button>
                      : <Link className="spot-pv" to={`/pivot/${l.pivot_id}`}>{head}</Link>}
                    {did.length > 0 && <span className="muted">{did.join("; ")}</span>}
                  </li>
                );
              })}
            </ul>
          ) : <p className="muted">{t("spot.pivotNone")}</p>}

          {(news.length > 0 || effects.length > 0 || ties.length > 0) && (
            <>
              <h3>{t("spot.story")}</h3>
              <ul className="spot-story">
                {news.slice(0, 2).map((n) => <li key={n.news_id}>{n.headline} <LangTag lang="en" /></li>)}
                {effects.slice(0, 2).map((e, i) => <li key={`e${i}`}>{e.note} <LangTag lang="en" /></li>)}
                {ties.slice(0, 2).map((r) => (
                  <li key={r.relationship_id}>
                    <span><b>{t(`pre.tie.${r.kind}` as never)}</b>: {playerName(r.person_id === player ? r.other_id : r.person_id)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
