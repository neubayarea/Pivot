// Key players (C19, #385): the eight players with the most xG + xA, from /players/stats (the
// verifier's per-player lines), each as one bar in two parts, his team's colour for xG and a lighter
// step for xA. A name opens his row in the Stats tab's player table.
import type { CSSProperties } from "react";
import { Link, useLocation } from "react-router-dom";
import type { PlayerReport } from "@pivot/contracts";
import { tabSearch } from "../../data/tab";
import { useT } from "../../i18n";
import { num, or0 } from "./fmt";

/** The top `n` by xG + xA, among players who played. */
export function topContributors(players: readonly PlayerReport[], n = 8): PlayerReport[] {
  const sum = (p: PlayerReport) => or0(p.stats?.xg) + or0(p.stats?.xa);
  return players.filter((p) => p.stats && or0(p.stats.minutes_played) > 0 && sum(p) > 0)
    .sort((a, b) => sum(b) - sum(a) || a.shirt_number - b.shirt_number)
    .slice(0, n);
}

export default function PlayerContrib({ players, short }: { players: readonly PlayerReport[]; short: Record<"home" | "away", string> }) {
  const t = useT();
  const { search } = useLocation();
  const top = topContributors(players);
  if (!top.length) return <p className="muted">{t("rp.pl.none")}</p>;
  const max = Math.max(...top.map((p) => or0(p.stats?.xg) + or0(p.stats?.xa)));
  return (
    <div className="rp-players">
      <ol className="rp-pl">
        {top.map((p) => {
          const xg = or0(p.stats?.xg), xa = or0(p.stats?.xa);
          return (
            <li key={p.player_id} style={{ "--tc": `var(--pv-${p.team})` } as CSSProperties}>
              <Link className="rp-pl-name" to={{ pathname: "/", search: tabSearch(search, "stats"), hash: `#pt-${p.player_id}` }}>
                <span className="num">{p.shirt_number}</span> {p.name} <small>{short[p.team]}</small>
              </Link>
              <span className="rp-pl-bar" style={{ width: `${((xg + xa) / max) * 100}%` }} role="img" aria-label={`xG ${num(xg)}, xA ${num(xa)}`}>
                {xg > 0 && <i className="xg" style={{ flexGrow: xg }} title={`xG ${num(xg)}`} />}
                {xa > 0 && <i className="xa" style={{ flexGrow: xa }} title={`xA ${num(xa)}`} />}
              </span>
              <span className="rp-pl-n num">{num(xg + xa)} <small>{num(xg)} + {num(xa)}</small></span>
            </li>
          );
        })}
      </ol>
      <p className="rp-key">
        <span className="k-xg" title={t("metric.xg.def")}>{t("metric.xg.short")}</span>
        <span className="k-xa" title={t("metric.xa.def")}>{t("metric.xa.short")}</span>
      </p>
    </div>
  );
}
