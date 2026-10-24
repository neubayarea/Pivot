import { useMatch, type TeamStats } from "../data/match";
import { useT } from "../i18n";

const ROWS: [keyof TeamStats, (v: number) => string][] = [
  ["possession", (v) => `${v}%`],
  ["shots", String],
  ["xg", (v) => v.toFixed(2)],
  ["pressures", String],
  ["finalThirdPasses", String],
];

export default function MatchStats() {
  const { stats } = useMatch();
  const t = useT();
  return (
    <div className="statlist">
      {ROWS.map(([key, fmt]) => {
        const h = stats.home[key];
        const a = stats.away[key];
        const total = h + a || 1;
        return (
          <div key={key} className="stat">
            <span className="nm">{t(`stats.${key}`)}</span>
            <span>{fmt(h)}</span>
            <span className="bar" aria-hidden="true">
              <i style={{ width: `${(h / total) * 100}%` }} />
              <i style={{ width: `${(a / total) * 100}%` }} />
            </span>
            <span className="r">{fmt(a)}</span>
          </div>
        );
      })}
    </div>
  );
}
