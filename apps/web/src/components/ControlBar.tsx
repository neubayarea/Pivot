// One control bar for every pitch that plays (Ax61): the full replay on the Live tab and the clips.
// Play/pause, back and on a step, a timeline with the goals and pivots on it (click one to go
// there), the time, and the speeds. The pitch's motion loop moves the thumb and the time on every
// screen frame through `inputRef`/`timeRef`, so the bar keeps up without re-rendering.
import { useRef, type KeyboardEvent, type ReactNode, type RefObject } from "react";
import { useT } from "../i18n";
import Segmented from "./Segmented";
import "../styles/control-bar.css";

export type BarMark = { t: number; kind: "goal" | "pivot" | "red" | "moment"; label: string; side?: "home" | "away" };

type Props = {
  playing: boolean;
  onPlaying: (playing: boolean) => void;
  value: number;
  min: number;
  max: number;
  onSeek: (t: number) => void;
  /** Seconds the back and on buttons (and ←/→) move. */
  step: number;
  speeds: readonly number[];
  speed: number;
  onSpeed: (speed: number) => void;
  marks: BarMark[];
  /** Clicking a mark goes this many seconds before it, so the move leading up to it is seen. */
  lead?: number;
  format: (t: number) => string;
  disabled?: boolean;
  inputRef?: RefObject<HTMLInputElement | null>;
  timeRef?: RefObject<HTMLSpanElement | null>;
  /** More buttons after the speeds (the clip's play-again). */
  children?: ReactNode;
};

export const speedLabel = (s: number) => `${s}×`;

/** Space/K plays and pauses, ←/→ move by `step` (Shift: five times that). True when the key was one of them. */
export function barKey(e: KeyboardEvent, { toggle, seekBy, step }: { toggle: () => void; seekBy: (d: number) => void; step: number }): boolean {
  const tag = (e.target as HTMLElement).tagName;
  if ((e.key === " " || e.key === "k" || e.key === "K") && tag !== "BUTTON") toggle();
  else if (e.key === "ArrowLeft" && tag !== "INPUT") seekBy(-step * (e.shiftKey ? 5 : 1));
  else if (e.key === "ArrowRight" && tag !== "INPUT") seekBy(step * (e.shiftKey ? 5 : 1));
  else return false;
  e.preventDefault();
  return true;
}

export default function ControlBar({ playing, onPlaying, value, min, max, onSeek, step, speeds, speed, onSpeed, marks,
  lead = 0, format, disabled = false, inputRef, timeRef, children }: Props) {
  const t = useT();
  const own = useRef<HTMLInputElement>(null);
  const input = inputRef ?? own;
  const pct = (s: number) => `${((s - min) / Math.max(1, max - min)) * 100}%`;
  const clamp = (s: number) => Math.min(max, Math.max(min, s));
  // A speed set elsewhere (the replay bar's 20× or 60×) still shows as picked.
  const options = (speeds.includes(speed) ? speeds : [...speeds, speed].sort((a, b) => a - b))
    .map((s) => ({ value: String(s), label: speedLabel(s) }));
  return (
    <div className="ctl" role="group" aria-label={t("ctl.label")}>
      <span className="ctl-btns">
        <button type="button" className="play" aria-label={t(playing ? "scrub.pause" : "scrub.play")} onClick={() => onPlaying(!playing)}
          disabled={disabled}>
          {playing ? "❚❚" : "▶"}
        </button>
        <button type="button" aria-label={t("ctl.back", { s: step })} title={t("ctl.back", { s: step })} disabled={disabled}
          onClick={() => onSeek(clamp(Number(input.current?.value ?? value) - step))}>−{step}s</button>
        <button type="button" aria-label={t("ctl.on", { s: step })} title={t("ctl.on", { s: step })} disabled={disabled}
          onClick={() => onSeek(clamp(Number(input.current?.value ?? value) + step))}>+{step}s</button>
      </span>
      <span className="ctl-track">
        <input ref={input} type="range" min={min} max={max} step="any" defaultValue={value} key={`${min}:${max}`}
          aria-label={t("scrub.time")} aria-valuetext={format(value)} disabled={disabled}
          onInput={(e) => onSeek(Number((e.target as HTMLInputElement).value))} />
        {marks.filter((m) => m.t >= min && m.t <= max).map((m) => (
          <button key={`${m.kind}${m.t}`} type="button" className={`ctl-mk ${m.kind}${m.side ? ` ${m.side}` : ""}`} style={{ left: pct(m.t) }}
            aria-label={m.label} title={m.label} disabled={disabled} onClick={() => onSeek(clamp(m.t - lead))}>
            <i />
          </button>
        ))}
      </span>
      <span className="ctl-time num" ref={timeRef}>{format(value)}</span>
      <Segmented label={t("playback.speed")} value={String(speed)} onChange={(v) => onSpeed(Number(v))} options={options} />
      {children}
    </div>
  );
}
