import { useId } from "react";
import type { MinuteMetric, Pivot1 as Pivot } from "@pivot/contracts";
import { useClock } from "../data/clock";
import type { KeyKind } from "../data/keyMoments";
import type { Side } from "../data/view";
import { useT } from "../i18n";
import { KeyMark } from "./KeyMoments";

type Props = {
  metrics: MinuteMetric[];
  pivots: Pivot[];
  homeLabel: string;
  awayLabel: string;
  /** The board's numbered moments (①②③): pivot ids in order, drawn as big buttons that open one. */
  numbered?: string[];
  selected?: string | null;
  onPick?: (pivotId: string) => void;
  /** Key moments (goals, red cards, ...): small marks on the midline, apart from the numbered pivots. */
  keys?: { id: string; t: number; kind: KeyKind; side: Side; label: string }[];
  keySelected?: string | null;
  onKey?: (id: string) => void;
  /** C11: the open pivot's before / after window, in seconds, shaded behind the line. */
  windowAt?: readonly [number, number] | null;
};

// Geometry follows the S1 mock in docs/design/matchday-programme.html.
const W = 780, H = 230, L = 34, R = 12, T = 28, B = 26;
const MID = T + (H - T - B) / 2;
const AMP = (H - T - B) / 2;
const y = (v: number) => MID - v * AMP;
const TICKS = [0, 15, 30, 45, 60, 75, 90];

/**
 * Momentum per half: home above the midline, away below; the second half restarts from zero.
 * The axis runs on elapsed minutes, so stoppage time takes room, but reads the match clock:
 * each tick sits where the clock showed it, and the second half starts at its real kick-off.
 */
export default function MomentumChart({ metrics, pivots, homeLabel, awayLabel, numbered, selected, onPick, keys = [], keySelected, onKey, windowAt }: Props) {
  const clip = useId().replace(/[^\w-]/g, "");
  const t = useT();
  const { periods, minute } = useClock();
  const ht = (periods.find((p) => p.period === 2)?.start_t ?? 45 * 60) / 60;
  const end = Math.max(ht + 45, ...metrics.map((m) => m.minute + 1), ...pivots.map((p) => p.minute + 1));
  const x = (m: number) => L + ((W - L - R) * m) / end;
  const tickAt = (c: number) => (c <= 45 ? c : ht + c - 45);
  const halves = [
    metrics.filter((m) => m.minute < ht).map((m) => [m.minute, m.momentum] as const),
    metrics.filter((m) => m.minute >= ht).map((m) => [m.minute, m.momentum] as const),
  ];
  if (halves[1].length) halves[1].unshift([ht, 0]);
  const last = metrics.at(-1);
  const area = halves
    .filter((h) => h.length > 1)
    .map((h) => `M${x(h[0][0])},${MID}${h.map(([t, v]) => ` L${x(t)},${y(v)}`).join("")} L${x(h.at(-1)![0])},${MID} Z`)
    .join(" ");
  const line = halves
    .filter((h) => h.length > 1)
    .map((h) => "M" + h.map(([t, v]) => `${x(t)},${y(v)}`).join(" L"))
    .join(" ");
  const summary = pivots
    .filter((p) => p.status === "confirmed")
    .map((p) => t("chart.towards", { minute: minute(p.minute), team: p.direction === "home" ? homeLabel : awayLabel }))
    .join(", ");

  return (
    <svg className="mom" viewBox={`0 0 ${W} ${H}`} role="group" aria-label={t("chart.label", { list: summary || t("chart.none") })}>
      <defs>
        <clipPath id={`${clip}up`}>
          <rect x={0} y={0} width={W} height={MID} />
        </clipPath>
        <clipPath id={`${clip}dn`}>
          <rect x={0} y={MID} width={W} height={H} />
        </clipPath>
      </defs>
      {windowAt && (
        <rect className="mom-win" x={x(windowAt[0] / 60)} y={T} width={Math.max(2, x(windowAt[1] / 60) - x(windowAt[0] / 60))} height={H - T - B} />
      )}
      <rect x={x(ht)} y={T} width={1} height={H - T - B} fill="var(--pv-hair)" />
      <text x={x(ht) + 4} y={T + 10} fontSize={11} fill="var(--pv-ink-2)">
        {t("chart.ht")}
      </text>
      <line x1={L} x2={W - R} y1={MID} y2={MID} stroke="var(--pv-ink)" strokeWidth={2} />
      {TICKS.map((t) => (
        <text key={t} x={x(tickAt(t))} y={H - 8} fontSize={11} textAnchor="middle" fill="var(--pv-ink-2)">
          {t}′
        </text>
      ))}
      <text x={4} y={T + 12} fontSize={11} fontWeight={700} fill="var(--pv-home)">
        {homeLabel}
      </text>
      <text x={4} y={H - B - 4} fontSize={11} fontWeight={700} fill="var(--pv-away)">
        {awayLabel}
      </text>
      <path d={area} fill="var(--pv-home)" fillOpacity={0.85} clipPath={`url(#${clip}up)`} />
      <path d={area} fill="var(--pv-away)" fillOpacity={0.85} clipPath={`url(#${clip}dn)`} />
      <path d={line} fill="none" stroke="var(--pv-ink)" strokeWidth={1.5} />
      {pivots.map((p) => {
        const pending = p.status === "pending";
        const label = `${minute(p.minute)}′`;
        const n = numbered?.indexOf(p.pivot_id) ?? -1;
        if (n >= 0 && onPick) {
          const cx = x(p.minute);
          const open = () => onPick(p.pivot_id);
          return (
            <g key={p.pivot_id} className={`mom-mk${p.pivot_id === selected ? " on" : ""}`} role="button" tabIndex={0}
              aria-pressed={p.pivot_id === selected} aria-label={t("moments.open", { n: n + 1, minute: minute(p.minute) })}
              onClick={open} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), open())}>
              <line x1={cx} x2={cx} y1={T + 2} y2={H - B} />
              <circle cx={cx} cy={T - 2} r={14} />
              <text x={cx} y={T + 3} textAnchor="middle">{n + 1}</text>
              <text className="mk-min" x={cx + 18} y={T - 4}>{label}</text>
            </g>
          );
        }
        const w = Math.max(34, 7 * label.length + 6);     // 45+2′ needs more room than 64′
        return (
          <g key={p.pivot_id} className={pending ? "mom-pending" : undefined}>
            <line
              x1={x(p.minute)} x2={x(p.minute)} y1={T} y2={H - B}
              stroke="var(--pv-red)" strokeWidth={pending ? 2 : 3} strokeDasharray={pending ? "4 4" : undefined}
            />
            <rect x={x(p.minute) - w / 2} y={T - 16} width={w} height={17} fill={pending ? "var(--pv-sheet)" : "var(--pv-red)"}
              stroke="var(--pv-red)" strokeWidth={pending ? 2 : 0} />
            <text x={x(p.minute)} y={T - 3} fontSize={12} fontWeight={700} textAnchor="middle"
              fill={pending ? "var(--pv-red)" : "var(--pv-on-red)"}>
              {label}
            </text>
          </g>
        );
      })}
      {keys.map((k) => {
        const kx = x(k.t / 60);
        const on = k.id === keySelected;
        const go = () => onKey?.(k.id);
        return (
          <g key={k.id} className={`mom-key${on ? " on" : ""}`} role={onKey ? "button" : undefined} tabIndex={onKey ? 0 : undefined}
            aria-pressed={onKey ? on : undefined} aria-label={k.label} onClick={go}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), go())}>
            <circle className="hit" cx={kx} cy={MID} r={11} />
            {on && <circle className="ring" cx={kx} cy={MID} r={9.5} />}
            <KeyMark kind={k.kind} side={k.side} x={kx} y={MID} size={on ? 1.25 : 1} />
          </g>
        );
      })}
      {last && (
        <>
          <rect x={x(last.minute) + 8} y={T} width={2} height={H - T - B} fill="var(--pv-hair)" />
          <circle cx={x(last.minute)} cy={y(last.momentum)} r={5} fill="var(--pv-gold)" stroke="var(--pv-ink)" strokeWidth={2} />
        </>
      )}
    </svg>
  );
}
