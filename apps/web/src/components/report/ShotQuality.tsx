// Shot quality (C19, #385), StatsBomb style. Every shot as a dot on one xG axis, a row per team
// (filled: scored; hollow: not), from /shots; then each team's xG split by where the chance came from,
// its xG per shot and its big chances (xG 0.3 or more), from the API's analysis.
import type { CSSProperties } from "react";
import type { ShotMapShot } from "@pivot/contracts";
import { SOURCES, type ShotQualityLine, type Side } from "../../data/analysis";
import { useT, type MessageKey } from "../../i18n";

const W = 1100, L = 120, R = 16, ROW = 56, TOP = 18;

/** Dots along an xG axis, nudged up and down out of each other's way (a simple beeswarm). */
export function swarm(xs: readonly number[], r: number): number[] {
  const placed: { x: number; y: number }[] = [];
  return xs.map((x) => {
    for (let k = 0; ; k++) {
      const y = k === 0 ? 0 : (k % 2 ? 1 : -1) * Math.ceil(k / 2) * (r * 2 + 1);
      if (Math.abs(y) > 18 || placed.every((p) => Math.hypot(p.x - x, p.y - y) >= r * 2 + 1)) {
        placed.push({ x, y });
        return y;
      }
    }
  });
}

export default function ShotQuality({ shots, quality, names, nameOf }: {
  shots: readonly ShotMapShot[]; quality: Record<Side, ShotQualityLine> | null; names: Record<Side, string>; nameOf: (id: string | null) => string;
}) {
  const t = useT();
  const top = Math.max(0.6, ...shots.map((s) => s.xg ?? 0));
  const x = (v: number) => L + (v / top) * (W - L - R);
  const ticks = [0, 0.1, 0.2, 0.3, 0.5, 0.75, 1].filter((v) => v <= top + 1e-9);
  const H = TOP + ROW * 2 + 28;
  const rows = (["home", "away"] as const).map((side) => {
    const own = shots.filter((s) => s.team === side && s.xg !== null).sort((a, b) => (a.xg ?? 0) - (b.xg ?? 0));
    const ys = swarm(own.map((s) => x(s.xg ?? 0)), 5);
    return { side, own, ys };
  });
  const srcMax = quality ? Math.max(...(["home", "away"] as const).map((s) => SOURCES.reduce((n, k) => n + quality[s].by_source[k], 0)), 0.5) : 1;
  return (
    <div className="rp-shots">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("rp.sq.label")}>
        <line x1={x(0.3)} x2={x(0.3)} y1={TOP - 6} y2={TOP + ROW * 2} className="rp-ref" />
        <text x={x(0.3) + 4} y={TOP} className="rp-axis">{t("rp.sq.big")}</text>
        {ticks.map((v) => <text key={v} x={x(v)} y={H - 6} textAnchor="middle" className="rp-axis">{v}</text>)}
        {rows.map(({ side, own, ys }, r) => {
          const cy = TOP + ROW * r + ROW / 2;
          return (
            <g key={side} style={{ color: `var(--pv-${side})` }}>
              <text x={L - 12} y={cy + 4} textAnchor="end" className="rp-row">{names[side]}</text>
              <line x1={L} x2={W - R} y1={cy} y2={cy} className="rp-grid" />
              {own.map((s, i) => (
                <circle key={s.event_id} cx={x(s.xg ?? 0)} cy={cy + ys[i]} r={5}
                  className={`rp-shot${s.outcome === "goal" ? " goal" : ""}`}>
                  <title>{`${s.clock_label.replace(/'/g, "′")} ${nameOf(s.player_id)}: xG ${(s.xg ?? 0).toFixed(2)}${s.outcome === "goal" ? ` · ${t("xg.keyGoal")}` : ""}`}</title>
                </circle>
              ))}
            </g>
          );
        })}
        <text x={L - 12} y={H - 6} textAnchor="end" className="rp-axis">{t("rp.sq.axis")}</text>
      </svg>
      <p className="rp-key">
        <span className="k-dot">{t("rp.sq.scored")}</span>
        <span className="k-ring">{t("rp.sq.missed")}</span>
      </p>
      {quality && (
        <div className="rp-src-bars">
          {(["home", "away"] as const).map((side) => {
            const q = quality[side];
            const total = SOURCES.reduce((n, k) => n + q.by_source[k], 0);
            return (
              <div key={side} className="rp-src-row" style={{ "--tc": `var(--pv-${side})` } as CSSProperties}>
                <span className="rp-row">{names[side]}</span>
                <span className="rp-stack" style={{ width: `${(total / srcMax) * 100}%` }} role="img"
                  aria-label={SOURCES.map((k) => `${t(`rp.src.${k}` as MessageKey)} ${q.by_source[k].toFixed(2)}`).join(", ")}>
                  {SOURCES.map((k, i) => q.by_source[k] > 0 && (
                    <i key={k} className={`s${i}`} style={{ flexGrow: q.by_source[k] }} title={`${t(`rp.src.${k}` as MessageKey)}: xG ${q.by_source[k].toFixed(2)}`}>
                      {q.by_source[k] / total >= 0.18 && <b>{t(`rp.src.${k}` as MessageKey)} {q.by_source[k].toFixed(2)}</b>}
                    </i>
                  ))}
                </span>
                <span className="rp-sq-nums">
                  <span title={t("metric.xg_per_shot.def")}>{t("metric.xg_per_shot.short")} <b className="num">{q.xg_per_shot.toFixed(2)}</b></span>
                  <span title={t("metric.big_chances.def")}>{t("metric.big_chances.short")} <b className="num">{q.big_chances}</b></span>
                  <span title={t("metric.shots.def")}>{t("metric.shots.short")} <b className="num">{q.shots}</b></span>
                </span>
              </div>
            );
          })}
          <p className="rp-key">
            {SOURCES.map((k, i) => <span key={k} className={`k-src s${i}`}>{t(`rp.src.${k}` as MessageKey)}</span>)}
          </p>
        </div>
      )}
    </div>
  );
}
