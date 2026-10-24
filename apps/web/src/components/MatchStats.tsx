import { useMatch, type TeamStats } from "../data/match";

const ROWS: [string, keyof TeamStats, (v: number) => string][] = [
  ["Possession", "possession", (v) => `${v}%`],
  ["Shots", "shots", String],
  ["xG", "xg", (v) => v.toFixed(2)],
  ["Pressures", "pressures", String],
  ["Final-third passes", "finalThirdPasses", String],
];

export default function MatchStats() {
  const { stats } = useMatch();
  return (
    <div className="statlist">
      {ROWS.map(([label, key, fmt]) => {
        const h = stats.home[key];
        const a = stats.away[key];
        const total = h + a || 1;
        return (
          <div key={key} className="stat">
            <span className="nm">{label}</span>
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
