import { useId } from "react";
import type { MinuteMetric, Pivot1 as Pivot } from "@pivot/contracts";

type Props = {
  metrics: MinuteMetric[];
  pivots: Pivot[];
  homeLabel: string;
  awayLabel: string;
};

// Geometry follows the S1 mock in docs/design/matchday-programme.html.
const W = 780, H = 220, L = 34, R = 12, T = 18, B = 26;
const MID = T + (H - T - B) / 2;
const AMP = (H - T - B) / 2;
const x = (minute: number) => L + ((W - L - R) * minute) / 90;
const y = (v: number) => MID - v * AMP;
const TICKS = [0, 15, 30, 45, 60, 75, 90];

/** Momentum per half: home above the midline, away below; the second half restarts from zero. */
export default function MomentumChart({ metrics, pivots, homeLabel, awayLabel }: Props) {
  const clip = useId().replace(/[^\w-]/g, "");
  const halves = [
    metrics.filter((m) => m.minute <= 45).map((m) => [m.minute, m.momentum] as const),
    metrics.filter((m) => m.minute > 45).map((m) => [m.minute, m.momentum] as const),
  ];
  if (halves[1].length) halves[1].unshift([45, 0]);
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
    .map((p) => `${p.minute}′ towards ${p.direction === "home" ? homeLabel : awayLabel}`)
    .join(", ");

  return (
    <svg className="mom" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Momentum chart. Pivots: ${summary || "none yet"}.`}>
      <defs>
        <clipPath id={`${clip}up`}>
          <rect x={0} y={0} width={W} height={MID} />
        </clipPath>
        <clipPath id={`${clip}dn`}>
          <rect x={0} y={MID} width={W} height={H} />
        </clipPath>
      </defs>
      <rect x={x(45)} y={T} width={1} height={H - T - B} fill="var(--pv-hair)" />
      <text x={x(45) + 4} y={T + 10} fontSize={11} fill="var(--pv-ink-2)">
        HT
      </text>
      <line x1={L} x2={W - R} y1={MID} y2={MID} stroke="var(--pv-ink)" strokeWidth={2} />
      {TICKS.map((t) => (
        <text key={t} x={x(t)} y={H - 8} fontSize={11} textAnchor="middle" fill="var(--pv-ink-2)">
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
        return (
          <g key={p.pivot_id} className={pending ? "mom-pending" : undefined}>
            <line
              x1={x(p.minute)} x2={x(p.minute)} y1={T} y2={H - B}
              stroke="var(--pv-red)" strokeWidth={pending ? 2 : 3} strokeDasharray={pending ? "4 4" : undefined}
            />
            <rect x={x(p.minute) - 17} y={T - 16} width={34} height={17} fill={pending ? "var(--pv-sheet)" : "var(--pv-red)"}
              stroke="var(--pv-red)" strokeWidth={pending ? 2 : 0} />
            <text x={x(p.minute)} y={T - 3} fontSize={12} fontWeight={700} textAnchor="middle"
              fill={pending ? "var(--pv-red)" : "var(--pv-on-red)"}>
              {p.minute}′
            </text>
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
