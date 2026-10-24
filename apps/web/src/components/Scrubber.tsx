import { clockLabel } from "../fixtures/demo-1021";

type Props = {
  window: [number, number];
  t: number;
  onChange: (t: number) => void;
  playing: boolean;
  onPlayingChange: (playing: boolean) => void;
  /** Minute marked in red on the track: the pivot itself. */
  pivotMinute: number;
  /** Seconds of the evidence events, drawn as gold ticks; `on` is the selected one. */
  marks: { t: number; on: boolean }[];
};

/** Pitch timeline: drag or play through the window around a pivot, one frame per second. */
export default function Scrubber({ window: [from, to], t, onChange, playing, onPlayingChange, pivotMinute, marks }: Props) {
  const pct = (s: number) => `${((s - from) / (to - from)) * 100}%`;
  return (
    <div className="scrub">
      <button type="button" className="play" aria-label={playing ? "Pause" : "Play"} onClick={() => onPlayingChange(!playing)}>
        {playing ? "❚❚" : "▶"}
      </button>
      <div className="track">
        {marks.map((m) => (
          <i key={m.t} className={`mk${m.on ? " on" : ""}`} style={{ left: pct(m.t) }} />
        ))}
        <i className="pv-mk" style={{ left: pct(pivotMinute * 60) }} />
        <input type="range" min={from} max={to} step={1} value={t} aria-label="Match time"
          aria-valuetext={clockLabel(t)} onChange={(e) => onChange(Number(e.target.value))} />
        <span style={{ left: 0 }}>{from / 60}′</span>
        <span className="pv-lbl" style={{ left: pct(pivotMinute * 60) }}>{pivotMinute}′</span>
        <span style={{ right: 0 }}>{to / 60}′</span>
      </div>
      <span className="now num">{clockLabel(t)}</span>
    </div>
  );
}
