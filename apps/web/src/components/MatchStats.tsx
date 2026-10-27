import type { TeamStatsReport } from "@pivot/contracts";
import { useMatch, type TeamStats } from "../data/match";
import { usePrefs } from "../i18n";

const ROWS: [keyof TeamStats, (v: number) => string][] = [
  ["possession", (v) => `${Math.round(v)}%`],
  ["shots", String],
  ["xg", (v) => v.toFixed(2)],
  ["pressures", String],
  ["finalThirdPasses", String],
];

// C11: the official MET values (#279) once the team stats are in, so this card, the full table
// and the AI's explanations quote the same numbers; the page's own count until then.
const MET: Record<keyof TeamStats, string> = {
  possession: "possession_pct", shots: "shots", xg: "xg", pressures: "pressures", finalThirdPasses: "passes_final_third",
};

export default function MatchStats({ report = null }: { report?: TeamStatsReport | null }) {
  const { stats } = useMatch();
  const { prefs, t } = usePrefs();
  // Fan mode names the same numbers in plain words: "Who had the ball", not "Possession".
  const label = prefs.audience === "fan" ? "stats.fan" : "stats";
  const fav = prefs.focus_team;
  const met = report?.scopes.find((s) => s.scope === "match");
  return (
    <div className="statlist">
      {ROWS.map(([key, fmt]) => {
        const h = met?.home[MET[key]] ?? stats.home[key];
        const a = met?.away[MET[key]] ?? stats.away[key];
        const total = h + a || 1;
        return (
          <div key={key} className="stat">
            <span className="nm">{t(`${label}.${key}`)}</span>
            <span className={fav === "home" ? "fav" : undefined}>{fmt(h)}</span>
            <span className="bar" aria-hidden="true">
              <i style={{ width: `${(h / total) * 100}%` }} />
              <i style={{ width: `${(a / total) * 100}%` }} />
            </span>
            <span className={`r${fav === "away" ? " fav" : ""}`}>{fmt(a)}</span>
          </div>
        );
      })}
    </div>
  );
}
