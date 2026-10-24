import { useMatch, type Speed } from "../data/match";
import Button from "./Button";
import Segmented from "./Segmented";

const SPEEDS = [
  { value: "1", label: "1×" },
  { value: "5", label: "5×" },
  { value: "20", label: "20×" },
  { value: "60", label: "60×" },
] as const;

/** Replay controls for the local fixture, so demo recordings can pause and rewind. */
export default function Playback() {
  const { match, playback } = useMatch();
  const done = match.status === "finished";
  return (
    <span className="playback">
      <span className="lbl">Replay</span>
      <Button onClick={() => playback.setPlaying(!playback.playing)} disabled={done}>
        {playback.playing ? "❚❚ Pause" : "▶ Play"}
      </Button>
      <Segmented
        label="Replay speed"
        options={SPEEDS}
        value={String(match.speed) as (typeof SPEEDS)[number]["value"]}
        onChange={(v) => playback.setSpeed(Number(v) as Speed)}
      />
      <Button variant="ghost" onClick={playback.restart}>
        Restart
      </Button>
    </span>
  );
}
