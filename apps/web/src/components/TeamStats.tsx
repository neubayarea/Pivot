// The team stats table (C11, data from Bx11 #279): MET-001 to MET-023 for both teams, grouped
// the Premier League way (attack, possession, defence, shape, physical), for the whole match or
// one half. The same numbers the AI cites and the Verifier checks, so the page and the
// explanations agree. Fans get the five that need no explaining; analysts get all of them.
import { useState, type CSSProperties } from "react";
import type { StatMetricInfo, TeamStatsReport, TeamStatsScope } from "@pivot/contracts";
import { useMatch } from "../data/match";
import { FAN5 } from "../data/persona";
import { useVizData, type VizState } from "../data/viz";
import { isMessageKey, usePrefs, type T } from "../i18n";
import Segmented from "./Segmented";

// C12: fans get the five plain ones (data/persona.ts), analysts all 23.
const FAN = new Set<string>(FAN5);

/** GET /api/matches/{id}/stats, up to the replay's or live match's second (whole minutes) when given. */
export function useTeamStats(matchId: string | null, upTo: number | null) {
  const q = upTo === null ? "" : `?up_to=${Math.floor(Math.max(0, upTo) / 60) * 60}`;
  return useVizData<TeamStatsReport>(matchId ? `/api/matches/${encodeURIComponent(matchId)}/stats${q}` : null);
}

/** "57%", "1.23", "104.2", "–" for no answer. */
export function statText(v: number | null | undefined, m: StatMetricInfo): string {
  if (v === null || v === undefined) return "–";
  if (m.unit === "pct") return `${v.toFixed(v % 1 ? 1 : 0)}%`;
  if (m.unit === "xg" || m.unit === "index") return v.toFixed(2);
  if (m.unit === "m" || m.unit === "km") return v.toFixed(1);
  return String(Math.round(v));
}

const label = (m: StatMetricInfo, fan: boolean, t: T) => {
  const k = fan ? `ts.fan.${m.metric}` : `ts.m.${m.metric}`;
  return isMessageKey(k) ? t(k) : isMessageKey(`ts.m.${m.metric}`) ? t(`ts.m.${m.metric}` as never) : m.label;
};

function Row({ m, s, fan, t }: { m: StatMetricInfo; s: TeamStatsScope; fan: boolean; t: T }) {
  const h = s.home[m.metric] ?? null;
  const a = s.away[m.metric] ?? null;
  // Which side the bar leans to; PPDA reads the other way round (fewer passes allowed is the harder press).
  const lower = m.metric === "ppda";
  const both = h !== null && a !== null && h + a > 0;
  const share = both ? (h! / (h! + a!)) * 100 : 50;
  const lead = h === null || a === null || h === a ? null : (h > a) !== lower ? "home" : "away";
  const name = label(m, fan, t);
  return (
    <tr>
      <td className={`h num${lead === "home" ? " win" : ""}`}>{statText(h, m)}</td>
      <th scope="row">
        <span title={m.description}>{name}</span>
        {both && (
          <span className="ts-bar" aria-hidden="true">
            <i style={{ width: `${share}%` }} />
            <i style={{ width: `${100 - share}%` }} />
          </span>
        )}
      </th>
      <td className={`a num${lead === "away" ? " win" : ""}`}>{statText(a, m)}</td>
    </tr>
  );
}

/** `only`: just these metrics, whoever is watching (the overview's core five); otherwise fans get FAN5, analysts all. */
export default function TeamStats({ state, only }: { state: VizState<TeamStatsReport>; only?: ReadonlySet<string> }) {
  const { teams } = useMatch();
  const { prefs, t } = usePrefs();
  const { data, error } = state;
  const [scope, setScope] = useState<TeamStatsScope["scope"]>("match");
  const fan = prefs.audience === "fan";
  if (!data) return <p className="muted" role="status">{t(error ? "ts.error" : "ts.loading")}</p>;
  const scopes = data.scopes.filter((s) => s.scope !== "window");
  const shown = scopes.find((s) => s.scope === scope) ?? scopes[0];
  if (!shown) return <p className="muted">{t("ts.error")}</p>;
  const keep = only ?? (fan ? FAN : null);
  const metrics = data.metrics.filter((m) => !keep || keep.has(m.metric));
  const groups = [...new Set(metrics.map((m) => m.group))];
  return (
    <div className="ts">
      {scopes.length > 1 && (
        <Segmented label={t("ts.scope")} value={shown.scope} onChange={setScope}
          options={scopes.map((s) => ({ value: s.scope, label: t(`ts.scope.${s.scope as Exclude<typeof s.scope, "window">}`) }))} />
      )}
      {/* C13: which column is which, the ♥ team marked in its kit colour. */}
      <p className="ts-teams" aria-hidden="true">
        {(["home", "away"] as const).map((side) => (
          <span key={side} className={prefs.focus_team === side ? "fav" : undefined} style={{ "--tc": `var(--pv-${side})` } as CSSProperties}>
            {teams[side].name}
            {prefs.focus_team === side && <small>{t("ts.yours")}</small>}
          </span>
        ))}
      </p>
      <div className="ts-groups">
        {groups.map((g) => (
          <table key={g} className="ts-table">
            <caption>{isMessageKey(`ts.group.${g}`) ? t(`ts.group.${g}` as never) : g}</caption>
            <thead className="sr-only">
              <tr><th scope="col">{teams.home.name}</th><th scope="col">{t("ts.title")}</th><th scope="col">{teams.away.name}</th></tr>
            </thead>
            <tbody>
              {metrics.filter((m) => m.group === g).map((m) => <Row key={m.metric} m={m} s={shown} fan={fan} t={t} />)}
            </tbody>
          </table>
        ))}
      </div>
    </div>
  );
}
