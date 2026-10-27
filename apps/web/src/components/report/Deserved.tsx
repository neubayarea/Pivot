// Deserved result (C19, #385), Understat / The Analyst xPts: the chance of each result if every shot
// went in with the probability its xG gives, simulated on the API, as one bar in three parts, and the
// expected points beside the real score.
import type { CSSProperties } from "react";
import type { MatchAnalysis, Side } from "../../data/analysis";
import { useT } from "../../i18n";

const pct = (v: number) => `${Math.round(v * 100)}%`;

/** The one-line verdict: the real score against the result the chances made most likely. */
export function deservedVerdict(d: MatchAnalysis["deserved"], score: Record<Side, number>): { key: "rp.dsv.match" | "rp.dsv.against" | "rp.dsv.draw"; side: Side | null; p: number } {
  const best = d.home_win >= d.away_win && d.home_win >= d.draw ? "home" : d.away_win >= d.draw ? "away" : null;
  const actual = score.home > score.away ? "home" : score.away > score.home ? "away" : null;
  const p = best === "home" ? d.home_win : best === "away" ? d.away_win : d.draw;
  if (best === actual) return { key: "rp.dsv.match", side: best, p };
  return best ? { key: "rp.dsv.against", side: best, p } : { key: "rp.dsv.draw", side: null, p };
}

export default function Deserved({ d, names, score }: { d: MatchAnalysis["deserved"]; names: Record<Side, string>; score: Record<Side, number> }) {
  const t = useT();
  // The points the real result gave: three for a win, one each for a draw.
  const pts = (s: Side) => { const o = s === "home" ? "away" : "home"; return score[s] > score[o] ? 3 : score[s] === score[o] ? 1 : 0; };
  const parts = [
    { k: "home", v: d.home_win, label: t("rp.dsv.win", { team: names.home }) },
    { k: "draw", v: d.draw, label: t("rp.dsv.drawShort") },
    { k: "away", v: d.away_win, label: t("rp.dsv.win", { team: names.away }) },
  ];
  return (
    <div className="rp-dsv">
      <div className="rp-dsv-bar" role="img" aria-label={parts.map((p) => `${p.label} ${pct(p.v)}`).join(", ")}>
        {parts.map((p) => (
          <span key={p.k} className={`seg ${p.k}`} style={{ flexGrow: Math.max(p.v, 0.001), "--c": p.k === "draw" ? "var(--pv-ink-3, #9AA1AC)" : `var(--pv-${p.k})` } as CSSProperties}
            title={`${p.label}: ${pct(p.v)}`}>
            {p.v >= 0.12 && <b className="num">{pct(p.v)}</b>}
          </span>
        ))}
      </div>
      <div className="rp-dsv-key">
        {parts.map((p) => <span key={p.k} className={p.k}>{p.label} <b className="num">{pct(p.v)}</b></span>)}
      </div>
      <dl className="rp-dsv-pts">
        {(["home", "away"] as const).map((s) => (
          <div key={s} style={{ "--tc": `var(--pv-${s})` } as CSSProperties}>
            <dt>{names[s]}</dt>
            <dd><span className="num rp-big">{d.xpts[s].toFixed(2)}</span> <span title={t("metric.xpts.def")}>{t("metric.xpts.short")}</span> <small>{t("rp.dsv.real", { n: pts(s) })}</small></dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
