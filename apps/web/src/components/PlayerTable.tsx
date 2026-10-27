// The analyst's player table on the Stats tab (C16, #366), FBref style: one row per player who
// played, sortable by any column, one team at a time. Every number is the API's own per-player
// line (/players/stats, the verifier's StatCalculator); nothing is worked out here. Each header
// carries its definition (metric.*), shown on hover and read out by screen readers.
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import type { PlayerReport } from "@pivot/contracts";
import { useMatch, type Side } from "../data/match";
import { usePersona, usePlayers } from "../data/persona";
import { usePrefs, type MessageKey } from "../i18n";
import Segmented from "./Segmented";
import { useTeamStats } from "./TeamStats";

export const PLAYER_COLS = ["minutes_played", "passes", "pass_accuracy_pct", "progressive_passes", "shots", "xg", "tackles_won", "interceptions", "rating"] as const;
type Col = (typeof PLAYER_COLS)[number];

/** The team's own line, from the team stats (the same report as the team-stats card), not a sum made here. */
const TEAM_COLS = new Set<Col>(["passes", "pass_accuracy_pct", "progressive_passes", "shots", "xg", "tackles_won", "interceptions"]);

const cell = (s: Partial<Record<Col, number | null>>, c: Col): string => {
  const v = s[c];
  if (v === null || v === undefined) return "–";
  if (c === "xg") return v.toFixed(2);
  if (c === "rating") return v.toFixed(1);
  if (c === "pass_accuracy_pct") return `${Math.round(v)}%`;
  return String(v);
};

/** Played this match, sorted by `col` (highest first, or lowest when `asc`), then by shirt number. */
export function playerRows(players: readonly PlayerReport[], side: Side, col: Col | null, asc: boolean): PlayerReport[] {
  const rows = players.filter((p) => p.team === side && p.stats && p.stats.minutes_played > 0);
  return rows.sort((a, b) => {
    if (col) {
      const d = (a.stats![col] ?? -1) - (b.stats![col] ?? -1);
      if (d) return asc ? d : -d;
    }
    return a.shirt_number - b.shirt_number;
  });
}

export default function PlayerTable({ upTo }: { upTo: number | null }) {
  const { match, teams } = useMatch();
  const { prefs, t } = usePrefs();
  const { side: mine } = usePersona();
  // C19: the report's player links land here as #pt-<id>: that player's team, his row in view.
  const { hash } = useLocation();
  const linked = hash.startsWith("#pt-") ? hash.slice(4) : null;
  const [side, setSide] = useState<Side>(mine ?? "home");
  const [col, setCol] = useState<Col | null>("rating");
  const [asc, setAsc] = useState(false);
  const { data, loading, error } = usePlayers(match.match_id, upTo);
  const linkedSide = linked ? data?.players.find((p) => p.player_id === linked)?.team : undefined;
  useEffect(() => {
    if (!linkedSide) return;
    setSide(linkedSide);
    requestAnimationFrame(() => document.getElementById(`pt-${linked}`)?.scrollIntoView({ block: "center" }));
  }, [linkedSide, linked]);
  const team = useTeamStats(match.match_id, upTo).data?.scopes.find((s) => s.scope === "match")?.[side];
  if (!data) return <p className="muted" role="status">{t(error ? "pt.error" : loading ? "pt.loading" : "pt.error")}</p>;
  const rows = playerRows(data.players, side, col, asc);
  const sortBy = (c: Col) => {
    if (c === col) setAsc(!asc);
    else { setCol(c); setAsc(false); }
  };

  return (
    <div className="pt">
      <Segmented label={t("pics.side")} value={side} onChange={setSide} options={[
        { value: "home", label: teams.home.name },
        { value: "away", label: teams.away.name },
      ]} />
      <div className="pt-scroll">
        <table className="pt-table">
          <caption className="sr-only">{t("pt.caption", { team: teams[side].name })}</caption>
          <thead>
            <tr>
              <th scope="col" className="pt-who">{t("pt.player")}</th>
              {PLAYER_COLS.map((c) => (
                <th key={c} scope="col" aria-sort={col === c ? (asc ? "ascending" : "descending") : "none"}>
                  <button type="button" title={t(`metric.${c}.def` as MessageKey)} onClick={() => sortBy(c)}>
                    {t(`metric.${c}.short` as MessageKey)}
                    <span aria-hidden="true" className="pt-arrow">{col === c ? (asc ? "▲" : "▼") : ""}</span>
                    <span className="sr-only">: {t(`metric.${c}.def` as MessageKey)}</span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.player_id} id={`pt-${p.player_id}`}
                className={[p.player_id === prefs.focus_player_id ? "on" : "", p.player_id === linked ? "linked" : ""].join(" ").trim() || undefined}>
                <th scope="row" className="pt-who">
                  <span className="num pt-shirt">{p.shirt_number}</span> {p.name} <small>{p.role}</small>
                </th>
                {PLAYER_COLS.map((c) => <td key={c} className="num">{cell(p.stats!, c)}</td>)}
              </tr>
            ))}
          </tbody>
          {team && (
            <tfoot>
              <tr>
                <th scope="row" className="pt-who">{t("pt.team", { team: teams[side].short_name })}</th>
                {PLAYER_COLS.map((c) => <td key={c} className="num">{TEAM_COLS.has(c) ? cell({ [c]: team[c] ?? null }, c) : ""}</td>)}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      <p className="muted pt-note">{t("pt.note")}</p>
    </div>
  );
}
