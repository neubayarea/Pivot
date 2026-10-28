// Deserved result (C19, #385), Understat / The Analyst xPts: the chance of each result if every shot
// went in with the probability its xG gives, simulated on the API, as one bar in three parts, and the
// expected points beside the real score.
import type { CSSProperties } from "react";
import { isNum, type MatchAnalysis, type Side } from "../../data/analysis";
import { useT } from "../../i18n";
import { num, or0, share } from "./fmt";

/** The one-line verdict: the real score against the result the chances made most likely; null without the three chances. */
export function deservedVerdict(d: MatchAnalysis["deserved"], score: Record<Side, number>): { key: "rp.dsv.match" | "rp.dsv.against" | "rp.dsv.draw" | "rp.dsv.drawMatch"; side: Side | null; p: number } | null {
  const { home_win: h, draw: x, away_win: a } = d;
  if (!isNum(h) || !isNum(x) || !isNum(a)) return null;
  const best = h >= a && h >= x ? "home" : a >= x ? "away" : null;
  const actual = score.home > score.away ? "home" : score.away > score.home ? "away" : null;
  const p = best === "home" ? h : best === "away" ? a : x;
  // A draw the likeliest result is said as a draw ("most likely a draw, 67%"), never as a win.
  if (!best) return { key: actual ? "rp.dsv.draw" : "rp.dsv.drawMatch", side: null, p };
  return { key: best === actual ? "rp.dsv.match" : "rp.dsv.against", side: best, p };
}

export default function Deserved({ d, names, score, live = false }: { d: MatchAnalysis["deserved"]; names: Record<Side, string>; score: Record<Side, number>; live?: boolean }) {
  const t = useT();
  // The points the real result gave: three for a win, one each for a draw.
  const pts = (s: Side) => { const o = s === "home" ? "away" : "home"; return score[s] > score[o] ? 3 : score[s] === score[o] ? 1 : 0; };
  const parts = [
    { k: "home", v: d.home_win, label: t("rp.dsv.win", { team: names.home }) },
    { k: "draw", v: d.draw, label: t("rp.dsv.drawShort") },
    { k: "away", v: d.away_win, label: t("rp.dsv.win", { team: names.away }) },
  ];
  const whole = parts.every((p) => isNum(p.v));
  return (
    <div className="rp-dsv">
      {whole && (
        <div className="rp-dsv-bar" role="img" aria-label={parts.map((p) => `${p.label} ${share(p.v)}`).join(", ")}>
          {parts.map((p) => (
            <span key={p.k} className={`seg ${p.k}`} style={{ flexGrow: Math.max(or0(p.v), 0.001), "--c": p.k === "draw" ? "var(--pv-ink-3, #9AA1AC)" : `var(--pv-${p.k})` } as CSSProperties}
              title={`${p.label}: ${share(p.v)}`}>
              {or0(p.v) >= 0.12 ? <b className="num">{share(p.v)}</b> : <span className="sr-only">{`${p.label} ${share(p.v)}`}</span>}
            </span>
          ))}
        </div>
      )}
      <div className="rp-dsv-key">
        {parts.map((p) => <span key={p.k} className={p.k}>{p.label} <b className="num">{share(p.v)}</b></span>)}
      </div>
      <dl className="rp-dsv-pts">
        {(["home", "away"] as const).map((s) => (
          <div key={s} style={{ "--tc": `var(--pv-${s})` } as CSSProperties}>
            <dt>{names[s]}</dt>
            <dd><span className="num rp-big">{num(d.xpts?.[s])}</span> <span title={t("metric.xpts.def")}>{t("metric.xpts.short")}</span> <small>{t(live ? "rp.dsv.realLive" : "rp.dsv.real", { n: pts(s) })}</small></dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
