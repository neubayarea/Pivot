import { clockLabel } from "../fixtures/demo-1021";
import { useT } from "../i18n";

type Props = {
  window: [number, number];
  t: number;
  onChange: (t: number) => void;
  playing: boolean;
  onPlayingChange: (playing: boolean) => void;
  /** Minutes marked in red on the track: the pivot itself on S2, every pivot so far in the replay bar. */
  pivotMinutes: number[];
  /** Seconds of the evidence events, drawn as gold ticks if inside the window; `on` is the selected one, `mine` the followed player's. */
  marks: { t: number; on: boolean; mine?: boolean }[];
};

/** Timeline: drag or play through a window of the match (around a pivot, or all of it), one second a step. */
export default function Scrubber({ window: [from, to], t, onChange, playing, onPlayingChange, pivotMinutes, marks }: Props) {
  const tr = useT();
  const pct = (s: number) => `${((s - from) / Math.max(1, to - from)) * 100}%`;
  // Anything outside the window would sit past the ends of the track, so it is not drawn.
  const inside = (s: number) => s >= from && s <= to;
  return (
    <div className="scrub">
      <button type="button" className="play" aria-label={tr(playing ? "scrub.pause" : "scrub.play")} onClick={() => onPlayingChange(!playing)}>
        {playing ? "❚❚" : "▶"}
      </button>
      <div className="track">
        {marks.filter((m) => inside(m.t)).map((m) => (
          <i key={m.t} className={`mk${m.on ? " on" : ""}${m.mine ? " mine" : ""}`} style={{ left: pct(m.t) }} />
        ))}
        {pivotMinutes.filter((m) => inside(m * 60)).map((m) => <i key={m} className="pv-mk" style={{ left: pct(m * 60) }} />)}
        <input type="range" min={from} max={to} step={1} value={t} aria-label={tr("scrub.time")}
          aria-valuetext={clockLabel(t)} onChange={(e) => onChange(Number(e.target.value))} />
        <span style={{ left: 0 }}>{Math.floor(from / 60)}′</span>
        {pivotMinutes.filter((m) => inside(m * 60)).map((m) => <span key={m} className="pv-lbl" style={{ left: pct(m * 60) }}>{m}′</span>)}
        <span style={{ right: 0 }}>{Math.ceil(to / 60)}′</span>
      </div>
      <span className="now num">{clockLabel(t)}</span>
    </div>
  );
}
