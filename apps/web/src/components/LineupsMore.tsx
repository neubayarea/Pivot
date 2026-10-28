// The line-ups tab's further parts (C21, #401). For analysts: what each substitution changed (the
// side's xG and field tilt in the 15 minutes before and after, /analysis `subs`) and the squad's
// ratings in bands. For fans: the player of the match and the substitutions in plain words.
// Every number comes from the API (data/lineupCards.ts only picks and sorts); nothing is shown
// until it answers.
import type { AnalysisSub, PlayerReport } from "@pivot/contracts";
import { useAnalysis } from "../data/analysis";
import { BANDS, MIN_MINUTES, cardStats, cardValue, ratingSpread, subImpact, type Side } from "../data/lineupCards";
import { useMatch } from "../data/match";
import { bestPlayer, usePlayers } from "../data/persona";
import { useT, type MessageKey, type T } from "../i18n";
import { Kit } from "./PreMatch";
import "../styles/lineups.css";

/** The clock reached, in whole minutes, for a live match or a replay; null for a finished one. */
export function useUpTo(): number | null {
  const { match, playback } = useMatch();
  return match.status === "finished" && !playback ? null : Math.floor(match.clock / 60) * 60;
}

/** The match's substitutions with what they changed, from /analysis; [] until it answers. */
export function useSubs(): AnalysisSub[] {
  const { match } = useMatch();
  const upTo = useUpTo();
  const { data } = useAnalysis(match.status === "scheduled" ? null : match.match_id, upTo);
  return ((data as unknown as { subs?: AnalysisSub[] } | null)?.subs) ?? [];
}

const num = (v: number | null, d = 2) => (v === null ? "–" : v.toFixed(d));
const pct = (v: number | null) => (v === null ? "–" : `${Math.round(v)}%`);

export function SubImpactTable() {
  const t = useT();
  const { teams } = useMatch();
  const rows = useSubs().map(subImpact);
  return (
    <section className="post-sec" aria-labelledby="lu-subs-hd" id="lu-subs">
      <header className="sec-hd">
        <h2 id="lu-subs-hd">{t("lu.subsTitle")}</h2>
        <p className="muted">{t("lu.subsNote")}</p>
      </header>
      <div className="card lu-subs">
        {rows.length === 0 ? <p className="muted">{t("lu.subsNone")}</p> : (
          <table className="lu-subs-t">
            <thead>
              <tr>
                <th scope="col">{t("lu.subs.minute")}</th>
                <th scope="col">{t("lu.subs.change")}</th>
                <th scope="col" className="num">{t("lu.subs.window")}</th>
                <th scope="col" className="num">{t("lu.subs.xg")}</th>
                <th scope="col" className="num">{t("lu.subs.xga")}</th>
                <th scope="col" className="num">{t("lu.subs.tilt")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ sub, xg, xga, tilt, tiltChange }) => (
                <tr key={sub.event_id}>
                  <td className="num">{sub.clock}′</td>
                  <td>
                    <span className="pre-who"><Kit side={sub.team as Side} />{teams[sub.team as Side].short_name}</span>{" "}
                    <span className="lu-sub-on">▲ {sub.player_on_name ?? "–"}</span>{" "}
                    <span className="lu-sub-off muted">▼ {sub.player_off_name ?? "–"}</span>
                  </td>
                  <td className="num">
                    {windowLabel(t, sub.minutes_before, sub.cut_before)} / {windowLabel(t, sub.minutes_after, sub.cut_after)}
                  </td>
                  <td className="num">{num(xg[0])} → {num(xg[1])}</td>
                  <td className="num">{num(xga[0])} → {num(xga[1])}</td>
                  <td className="num">
                    {pct(tilt[0])} → {pct(tilt[1])}
                    {tiltChange !== null && <small className={tiltChange > 0 ? "up" : tiltChange < 0 ? "down" : undefined}>
                      {" "}({tiltChange > 0 ? "+" : ""}{Math.round(tiltChange)})</small>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

/** "15′", or "8′ (half-time)" for a window that stopped short. */
function windowLabel(t: T, minutes: number, cut: AnalysisSub["cut_before"]): string {
  const m = `${Math.round(minutes)}′`;
  return cut ? `${m} (${t(`lu.cut.${cut}` as MessageKey)})` : m;
}

export function RatingSpread() {
  const t = useT();
  const { match, teams } = useMatch();
  const players = usePlayers(match.status === "scheduled" ? null : match.match_id, useUpTo()).data?.players ?? [];
  const spread = ratingSpread(players);
  const most = Math.max(1, ...spread.home, ...spread.away);
  if (!spread.home.some(Boolean) && !spread.away.some(Boolean)) return null;
  return (
    <section className="post-sec" aria-labelledby="lu-spread-hd" id="lu-spread">
      <header className="sec-hd">
        <h2 id="lu-spread-hd">{t("lu.spreadTitle")}</h2>
        <p className="muted">{t("lu.spreadNote", { n: MIN_MINUTES })}</p>
      </header>
      <div className="card lu-spread">
        <ol className="lu-bands" aria-label={t("lu.spreadTitle")}>
          {BANDS.map((b, i) => (
            <li key={b.label}>
              <span className="lu-bars">
                {(["home", "away"] as Side[]).map((s) => (
                  <i key={s} className={s} style={{ height: `${(100 * spread[s][i]) / most}%` }}
                    title={t("lu.spreadBar", { team: teams[s].name, n: spread[s][i], band: b.label })}>
                    {spread[s][i] > 0 && <b className="num">{spread[s][i]}</b>}
                  </i>
                ))}
              </span>
              <span className="lu-band num">{b.label}</span>
            </li>
          ))}
        </ol>
        <p className="lu-legend">
          {(["home", "away"] as Side[]).map((s) => <span key={s} className="pre-who"><Kit side={s} />{teams[s].name}</span>)}
        </p>
      </div>
    </section>
  );
}

/** The fan's two: the player of the match and the substitutions. */
export function FanLineupExtras() {
  const t = useT();
  const { match, teams } = useMatch();
  const players = usePlayers(match.status === "scheduled" ? null : match.match_id, useUpTo()).data?.players ?? [];
  const best = bestPlayer(players);
  const subs = useSubs();
  if (!best && !subs.length) return null;
  return (
    <section className="post-sec" aria-labelledby="lu-fan-hd" id="lu-fan">
      <header className="sec-hd"><h2 id="lu-fan-hd">{t(match.status === "finished" ? "lu.motm" : "lu.motmSoFar")}</h2></header>
      <div className="lu-fan">
        {best && <BestCard p={best} t={t} />}
        {subs.length > 0 && (
          <div className="card lu-fan-subs">
            <h3>{t("lu.fanSubsTitle")}</h3>
            <ul className="pre-list">
              {subs.map((s) => (
                <li key={s.event_id}>
                  <span className="num">{s.clock}′</span>
                  <span className="pre-who"><Kit side={s.team as Side} />{teams[s.team as Side].short_name}</span>
                  <span>{t("lu.fanSub", { on: s.player_on_name ?? "–", off: s.player_off_name ?? "–" })}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}

function BestCard({ p, t }: { p: PlayerReport; t: T }) {
  const { teams } = useMatch();
  return (
    <div className="card lu-best">
      <p className="lu-best-name"><Kit side={p.team} />{p.name} <span className="muted">· {teams[p.team].name}</span></p>
      <p className="lu-best-rating num" aria-label={t("lu.rating", { n: p.stats!.rating.toFixed(1) })}>{p.stats!.rating.toFixed(1)}</p>
      <PlayerNumbers p={p} t={t} />
    </div>
  );
}

/** The card for a hovered player on the formation pitch. */
export function PlayerHoverCard({ p }: { p: PlayerReport }) {
  const t = useT();
  const { teams } = useMatch();
  return (
    <>
      <p className="lu-card-name"><Kit side={p.team} />{p.name} <span className="muted">{p.role} · {teams[p.team].short_name}</span></p>
      <PlayerNumbers p={p} t={t} />
    </>
  );
}

/** Minutes, rating and the three stats for the player's role: the hover card and the player of the match. */
export function PlayerNumbers({ p, t }: { p: PlayerReport; t: T }) {
  if (!p.stats) return <p className="muted">{t("lu.cardNone")}</p>;
  return (
    <dl className="lu-card-stats">
      <div><dt>{t("lu.cardMin")}</dt><dd className="num">{p.stats.minutes_played}′</dd></div>
      <div><dt>{t("metric.rating.short")}</dt><dd className="num">{p.stats.rating.toFixed(1)}</dd></div>
      {cardStats(p).map(({ key, value }) => (
        <div key={key}><dt>{t(`lu.stat.${key}` as MessageKey)}</dt><dd className="num">{cardValue(key, value)}</dd></div>
      ))}
    </dl>
  );
}
