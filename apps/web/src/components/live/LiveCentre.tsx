// The live centre on the Replay / Live tab (C21, #401), Opta live-centre style.
//  - Fan: one sentence on who is on top now (the run of play over the last ten minutes) and the
//    momentum line.
//  - Analyst: the last ten minutes' xG, field tilt, PPDA and possession for both teams (the verifier's
//    team stats over that window, /stats?from=&to=), each with a line of the five-minute blocks once
//    the API sends them (/analysis rolling); a card for each new shot with its xG, where and how it
//    was taken; and the deserved result so far.
// No number here is worked out on the page; a part whose numbers are not there is left out.
import { useEffect, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import type { MinuteMetric, Pivot1 as Pivot, ShotMapShot, TeamStatsReport } from "@pivot/contracts";
import { isNum, useAnalysis, type Side } from "../../data/analysis";
import { useClock } from "../../data/clock";
import { useMatch } from "../../data/match";
import { usePersona } from "../../data/persona";
import { useVizData } from "../../data/viz";
import { useT, type MessageKey } from "../../i18n";
import MomentumChart from "../MomentumChart";
import PostMatchReport from "../report/PostMatchReport";
import ReportBoundary from "../report/ReportBoundary";
import { num, or0, pct } from "../report/fmt";
import { useShotMap } from "../viz";
import "../../styles/report.css";

/** The run of play over the last `span` minutes: who is on top, or null when it is even or unknown. */
export function onTopNow(metrics: readonly MinuteMetric[], minute: number, span = 10): Side | null {
  const recent = metrics.filter((m) => m.minute > minute - span && m.minute <= minute);
  if (recent.length < 3) return null;
  const avg = recent.reduce((n, m) => n + m.momentum, 0) / recent.length;
  return avg > 0.08 ? "home" : avg < -0.08 ? "away" : null;
}

const LIVE_METRICS = [["xg", "xg"], ["field_tilt_pct", "field_tilt"], ["ppda", "ppda"], ["possession_pct", "possession_pct"]] as const;
type RollKey = (typeof LIVE_METRICS)[number][0];
type Rolling = { from: number; to: number; home: Record<RollKey, number | null>; away: Record<RollKey, number | null> }[];

const show = (k: RollKey, v: number | null | undefined) => (k === "xg" ? num(v) : k === "ppda" ? num(v, 1) : pct(v));

/** A small line of the five-minute blocks, home and away, for one metric. */
function Spark({ rows, k }: { rows: Rolling; k: RollKey }) {
  const W = 120, H = 30;
  const vals = rows.flatMap((r) => [r.home[k], r.away[k]]).filter(isNum);
  if (rows.length < 2 || !vals.length) return null;
  const top = Math.max(...vals, k === "xg" ? 0.2 : 1);
  const line = (s: Side) => rows.map((r, i) => `${i ? "L" : "M"}${(i / (rows.length - 1)) * W},${H - 2 - (or0(r[s][k]) / top) * (H - 4)}`).join(" ");
  return (
    <svg className="lc-spark" viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
      <path d={line("home")} style={{ stroke: "var(--pv-home)" }} />
      <path d={line("away")} style={{ stroke: "var(--pv-away)" }} />
    </svg>
  );
}

function LiveMetrics({ upToMin }: { upToMin: number }) {
  const { match, teams } = useMatch();
  const t = useT();
  const { minute: clockOf } = useClock();
  const from = Math.max(0, upToMin - 10);
  const win = useVizData<TeamStatsReport>(upToMin > 0 ? `/api/matches/${encodeURIComponent(match.match_id)}/stats?from=${from}&to=${upToMin}` : null);
  const analysis = useAnalysis(match.match_id, upToMin * 60);
  // Whole five-minute blocks only: the block still being played has nulls and would draw a false dip.
  const rolling = (analysis.data as unknown as { rolling?: Rolling } | null)?.rolling?.filter((r) => r.to - r.from === 5 && r.to <= upToMin).slice(-8) ?? [];
  const scope = win.data?.scopes[0];
  if (!scope) return null;
  return (
    <section className="lc-card lc-metrics" aria-labelledby="lc-metrics-hd">
      <header className="rp-hd">
        <h3 id="lc-metrics-hd">{t("lc.metrics.title", { from: clockOf(from), to: clockOf(upToMin) })}</h3>
        <span className="rp-live">{t("rp.soFar")}</span>
      </header>
      <dl className="lc-grid">
        {LIVE_METRICS.map(([k, key]) => {
          const h = scope.home[k] ?? null, a = scope.away[k] ?? null;
          return (
            <div key={k} className="lc-m" title={t(`metric.${key}.def` as MessageKey)}>
              <dt>{t(`metric.${key}.short` as MessageKey)}</dt>
              <dd>
                <span className="num" style={{ color: "var(--pv-home)" } as CSSProperties} aria-label={`${teams.home.short_name} ${show(k, h)}`}>{show(k, h)}</span>
                <span className="num" style={{ color: "var(--pv-away)" } as CSSProperties} aria-label={`${teams.away.short_name} ${show(k, a)}`}>{show(k, a)}</span>
              </dd>
              <Spark rows={rolling} k={k} />
            </div>
          );
        })}
      </dl>
      <p className="rp-src">{t(rolling.length >= 2 ? "lc.metrics.srcRolling" : "lc.metrics.src")}</p>
    </section>
  );
}

/** A card for the shot just taken: who, xG, where from, how. */
function ShotCard({ shot, onClose }: { shot: ShotMapShot; onClose: () => void }) {
  const { teams, playerName } = useMatch();
  const t = useT();
  const W = 120, H = 78;
  return (
    <aside className="lc-shot" role="status" style={{ "--tc": `var(--pv-${shot.team})` } as CSSProperties}>
      <button type="button" className="lc-x" aria-label={t("lc.shot.close")} onClick={onClose}>×</button>
      <p className="lc-shot-k">{shot.clock_label.replace(/'/g, "′")} · {teams[shot.team].short_name} · {t(shot.outcome === "goal" ? "xg.keyGoal" : "lc.shot.title")}</p>
      <p className="lc-shot-who">{playerName(shot.player_id)}</p>
      <div className="lc-shot-bd">
        <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
          <rect x={1} y={1} width={W - 2} height={H - 2} rx={4} className="lc-turf" />
          <line x1={W / 2} x2={W / 2} y1={1} y2={H - 1} className="lc-turf-line" />
          <circle cx={(shot.team === "home" ? shot.x : 105 - shot.x) / 105 * W} cy={(shot.team === "home" ? shot.y : 68 - shot.y) / 68 * H} r={4} className="lc-dot" />
        </svg>
        <dl>
          <dt>{t("metric.xg.short")}</dt><dd className="num lc-xg">{num(shot.xg)}</dd>
          {shot.body_part && <><dt>{t("lc.shot.body")}</dt><dd>{t(`lc.body.${shot.body_part}` as MessageKey)}</dd></>}
          {shot.play_pattern && <><dt>{t("lc.shot.situation")}</dt><dd>{t(`lc.pattern.${shot.play_pattern}` as MessageKey)}</dd></>}
        </dl>
      </div>
    </aside>
  );
}

/**
 * The newest shot's card: it opens when a shot from the last minute and a half of play arrives and
 * stays eight seconds (real time, so a replay at 20× still shows it), or until closed.
 */
function ShotPopups({ upTo }: { upTo: number }) {
  const { match } = useMatch();
  const shots = useShotMap(match.match_id, { upTo, stepS: 10 });
  const [shown, setShown] = useState<ShotMapShot | null>(null);
  const [seen, setSeen] = useState<string | null>(null);
  const last = shots.data?.shots.filter((s) => s.t <= upTo).sort((a, b) => b.t - a.t)[0];
  useEffect(() => {
    if (!last || last.event_id === seen) return;
    setSeen(last.event_id);
    if (upTo - last.t <= 90) setShown(last);
  }, [last, seen, upTo]);
  useEffect(() => {
    if (!shown) return;
    const id = window.setTimeout(() => setShown(null), 8000);
    return () => window.clearTimeout(id);
  }, [shown]);
  if (!shown) return null;
  // On the page itself, so it stays in the corner of the screen whatever the section around it does.
  return createPortal(<ShotCard key={shown.event_id} shot={shown} onClose={() => setShown(null)} />, document.body);
}

export default function LiveCentre({ moments, upTo }: { moments: Pivot[]; upTo: number | null }) {
  const { match, teams, metrics, pivots } = useMatch();
  const t = useT();
  const { fan } = usePersona();
  const { at } = useClock();
  if (match.status === "scheduled") return null;
  const now = upTo ?? match.clock;
  const minute = Math.floor(now / 60);
  const top = onTopNow(metrics, minute);
  const sentence = top ? t(upTo === null ? "lc.top.end" : "lc.top.now", { team: teams[top].name }) : t(upTo === null ? "lc.top.evenEnd" : "lc.top.even");

  if (fan) {
    return (
      <section className="live-sec lc" aria-labelledby="lc-fan-hd">
        <header className="live-hd">
          <h2 id="lc-fan-hd">{t("lc.fan.title")}</h2>
          <p className="lc-now">{sentence}</p>
        </header>
        {metrics.length > 0 && (
          <div className="card">
            <MomentumChart metrics={metrics} pivots={pivots} homeLabel={teams.home.short_name} awayLabel={teams.away.short_name} numbered={moments.map((p) => p.pivot_id)} />
          </div>
        )}
      </section>
    );
  }
  return (
    <section className="live-sec lc" aria-labelledby="lc-an-hd">
      <header className="live-hd">
        <h2 id="lc-an-hd">{t(upTo === null ? "lc.an.titleEnd" : "lc.an.title", { minute: at(now) })}</h2>
        <p className="lc-now">{sentence}</p>
      </header>
      <ReportBoundary resetKey={`${match.match_id}:${minute}`}>
        <div className="lc-row">
          <div className="lc-col">
            <LiveMetrics upToMin={minute} />
            {metrics.length > 0 && (
              <div className="lc-card">
                <MomentumChart metrics={metrics} pivots={pivots} homeLabel={teams.home.short_name} awayLabel={teams.away.short_name} numbered={moments.map((p) => p.pivot_id)} />
              </div>
            )}
          </div>
          <PostMatchReport parts={["deserved"]} moments={moments} upTo={upTo === null ? null : minute * 60} />
        </div>
      </ReportBoundary>
      {upTo !== null && <ReportBoundary resetKey={match.match_id}><ShotPopups upTo={upTo} /></ReportBoundary>}
    </section>
  );
}
