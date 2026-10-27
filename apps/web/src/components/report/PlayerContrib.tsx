// Key players (C19, #385): the eight players with the most xG + xA, from /players/stats (the
// verifier's per-player lines), each as one bar in two parts, his team's colour for xG and a lighter
// step for xA. A name opens his row in the Stats tab's player table.
import type { CSSProperties } from "react";
import { Link, useLocation } from "react-router-dom";
import type { PlayerReport } from "@pivot/contracts";
import { tabSearch } from "../../data/tab";
import { useT } from "../../i18n";

/** The top `n` by xG + xA, among players who played. */
export function topContributors(players: readonly PlayerReport[], n = 8): PlayerReport[] {
  return players.filter((p) => p.stats && p.stats.minutes_played > 0 && p.stats.xg + p.stats.xa > 0)
    .sort((a, b) => b.stats!.xg + b.stats!.xa - (a.stats!.xg + a.stats!.xa) || a.shirt_number - b.shirt_number)
    .slice(0, n);
}

export default function PlayerContrib({ players, short }: { players: readonly PlayerReport[]; short: Record<"home" | "away", string> }) {
  const t = useT();
  const { search } = useLocation();
  const top = topContributors(players);
  if (!top.length) return <p className="muted">{t("rp.pl.none")}</p>;
  const max = Math.max(...top.map((p) => p.stats!.xg + p.stats!.xa));
  return (
    <div className="rp-players">
      <ol className="rp-pl">
        {top.map((p) => {
          const s = p.stats!;
          return (
            <li key={p.player_id} style={{ "--tc": `var(--pv-${p.team})` } as CSSProperties}>
              <Link className="rp-pl-name" to={{ pathname: "/", search: tabSearch(search, "stats"), hash: `#pt-${p.player_id}` }}>
                <span className="num">{p.shirt_number}</span> {p.name} <small>{short[p.team]}</small>
              </Link>
              <span className="rp-pl-bar" style={{ width: `${((s.xg + s.xa) / max) * 100}%` }} role="img" aria-label={`xG ${s.xg.toFixed(2)}, xA ${s.xa.toFixed(2)}`}>
                {s.xg > 0 && <i className="xg" style={{ flexGrow: s.xg }} title={`xG ${s.xg.toFixed(2)}`} />}
                {s.xa > 0 && <i className="xa" style={{ flexGrow: s.xa }} title={`xA ${s.xa.toFixed(2)}`} />}
              </span>
              <span className="rp-pl-n num">{(s.xg + s.xa).toFixed(2)} <small>{s.xg.toFixed(2)} + {s.xa.toFixed(2)}</small></span>
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
