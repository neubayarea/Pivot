// Shot map (Bx12): every shot of both teams on one pitch, home attacking to the right and away to
// the left. Analyst: circle size is the chance's xG and the tooltip gives it. Fan: one size, no xG,
// and the legend says in words what each mark means. Clicking a shot hands its event id to the
// page (`onPick`), which can open the clip.
import type { KeyboardEvent } from "react";
import type { ShotMap as ShotMapData, ShotMapShot } from "@pivot/contracts";
import type { Side, SquadPlayer } from "../../data/view";
import { usePrefs, type MessageKey } from "../../i18n";
import { VizPitch, minuteText, teamColor, toPx, whoFrom } from "./pitch";
import "../../styles/viz.css";

type Outcome = NonNullable<ShotMapShot["outcome"]>;
const OUTCOMES: Outcome[] = ["goal", "saved", "post", "off_target", "blocked", "disallowed"];

export function shotRadius(xg: number | null | undefined, fan: boolean): number {
  return fan ? 7 : 4 + 18 * Math.sqrt(Math.max(xg ?? 0, 0));
}

function Mark({ s, fan, label, on, onPick }: {
  s: ShotMapShot; fan: boolean; label: string; on: boolean; onPick?: (eventId: string) => void;
}) {
  const [x, y] = toPx(s.x, s.y, s.team === "away");
  const r = shotRadius(s.xg, fan);
  const color = teamColor(s.team);
  const pick = onPick ? () => onPick(s.event_id) : undefined;
  // C11: a clickable shot is a button for the keyboard and screen readers too (Enter or Space picks it).
  const common = {
    className: `viz-shot${s.outcome ? ` o-${s.outcome}` : ""}${on ? " on" : ""}`, onClick: pick, tabIndex: pick ? 0 : undefined,
    role: pick ? "button" : undefined, "aria-label": pick ? label : undefined, "aria-pressed": pick ? on : undefined,
    onKeyDown: pick ? (e: KeyboardEvent<SVGGElement>) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), pick()) : undefined,
  };
  if (s.outcome === "blocked") {
    return (
      <g {...common}>
        <title>{label}</title>
        <path d={`M${x - r * 0.7},${y - r * 0.7}L${x + r * 0.7},${y + r * 0.7}M${x - r * 0.7},${y + r * 0.7}L${x + r * 0.7},${y - r * 0.7}`}
          stroke={color} strokeWidth={3} />
      </g>
    );
  }
  const goal = s.outcome === "goal";
  const filled = goal || s.outcome === "saved";
  let line = null;
  if (goal && s.end_x !== null && s.end_x !== undefined && s.end_y !== null && s.end_y !== undefined) {
    const [ex, ey] = toPx(s.end_x, s.end_y, s.team === "away");
    line = <line x1={x} y1={y} x2={ex} y2={ey} stroke={color} strokeWidth={2} strokeDasharray="5 3" />;
  }
  return (
    <g {...common}>
      <title>{label}</title>
      {line}
      {/* C13 UX: no yellow (yellow is the AI's); a goal is the team's colour with an ink ring and a white centre. */}
      <circle cx={x} cy={y} r={r} fill={filled ? color : "none"} fillOpacity={filled ? (goal ? 1 : 0.85) : undefined}
        stroke={goal ? "var(--pv-ink)" : color} strokeWidth={goal ? 3 : on ? 4 : 2} />
      {goal && <circle cx={x} cy={y} r={Math.max(2.5, r * 0.35)} fill="#FFFFFF" pointerEvents="none" />}
    </g>
  );
}

export type ShotMapProps = {
  data: ShotMapData;
  squads?: Record<Side, SquadPlayer[]>;
  teamNames?: Record<Side, string>;
  /** The shot to ring, e.g. the one whose clip is open. */
  selected?: string | null;
  onPick?: (eventId: string) => void;
};

export default function ShotMap({ data, squads, teamNames, selected = null, onPick }: ShotMapProps) {
  const { prefs, t } = usePrefs();
  const fan = prefs.audience === "fan";
  const who = whoFrom(squads);
  const names = teamNames ?? { home: t("viz.home"), away: t("viz.away") };
  const outcome = (o: ShotMapShot["outcome"]) => t(`viz.outcome.${o ?? "off_target"}` as MessageKey);
  const label = (s: ShotMapShot) => {
    const vars = { minute: minuteText(s.clock_label), player: who(s.player_id).name, outcome: outcome(s.outcome),
                   xg: (s.xg ?? 0).toFixed(2) };
    return t(fan ? "viz.shots.tipFan" : "viz.shots.tip", vars);
  };
  const summary = (side: Side) => {
    const mine = data.shots.filter((s) => s.team === side);
    const vars = { team: names[side], shots: mine.length, goals: mine.filter((s) => s.outcome === "goal").length,
                   xg: mine.reduce((a, s) => a + (s.xg ?? 0), 0).toFixed(2) };
    return t(fan ? "viz.shots.summaryFan" : "viz.shots.summary", vars);
  };
  // big chances underneath, so a small one stays clickable on top
  const order = [...data.shots].sort((a, b) => (b.xg ?? 0) - (a.xg ?? 0));
  return (
    <figure className="viz viz-shots">
      <figcaption>
        <b>{t("viz.shots.title")}</b>
        <span className="viz-sides">
          <span className="viz-side home">{summary("home")}</span>
          <span className="viz-side away">{summary("away")}</span>
        </span>
      </figcaption>
      <VizPitch label={t("viz.shots.label", { home: names.home, away: names.away })}>
        {order.map((s) => (
          <Mark key={s.event_id} s={s} fan={fan} label={label(s)} on={s.event_id === selected} onPick={onPick} />
        ))}
      </VizPitch>
      {data.shots.length === 0 && <p className="viz-empty">{t("viz.shots.empty")}</p>}
      <ul className="viz-legend">
        {OUTCOMES.filter((o) => o !== "disallowed" || data.shots.some((s) => s.outcome === o)).map((o) => (
          <li key={o} className={`viz-key k-${o}`}><i aria-hidden="true" />{outcome(o)}</li>
        ))}
        <li className="viz-note">{t(fan ? "viz.shots.legendFan" : "viz.shots.legend")}</li>
      </ul>
    </figure>
  );
}
