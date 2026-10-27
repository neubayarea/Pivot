import { useMatch, type Speed } from "../data/match";
import { useT } from "../i18n";
import Button from "./Button";
import Scrubber from "./Scrubber";
import Segmented from "./Segmented";
import Stamp from "./Stamp";

const SPEEDS = [
  { value: "1", label: "1×" },
  { value: "5", label: "5×" },
  { value: "20", label: "20×" },
  { value: "60", label: "60×" },
] as const;

/**
 * The replay bar under the top bar, on every page while a replay runs (the fixture, or Start demo
 * on a stored match): play/pause, a timeline over the whole match, speed and restart. Dragging the
 * timeline moves the one replay clock, so the score, momentum, events, pivots and stats all follow,
 * backwards too. Hidden on the live feed. On the simulated live match (C14) it says so, runs at 1x
 * on the wall clock, and offers "Back to live" once the viewer has moved off it.
 */
export default function Playback() {
  const { match, events, pivots, playback } = useMatch();
  const t = useT();
  if (!playback) return null;
  const play = (on: boolean) => {
    if (on && match.clock >= playback.end) playback.seek(0);    // play again from kick-off
    playback.setPlaying(on);
  };
  const goals = events.filter((e) => e.type === "shot" && e.shot_outcome === "goal");
  const live = playback.goLive;
  const name = t(live ? "playback.simLive" : "playback.replay");
  return (
    <div className="playback" role="region" aria-label={name}>
      {live ? <Stamp tone="live">{name}</Stamp> : <span className="lbl">{name}</span>}
      <Scrubber window={[0, playback.end]} t={Math.floor(match.clock)} onChange={playback.seek}
        playing={playback.playing} onPlayingChange={play}
        pivotMinutes={[...new Set(pivots.map((p) => p.minute))]} marks={goals.map((e) => ({ t: e.t, on: false }))} />
      {live ? (
        <Button variant="ghost" onClick={live}>
          {t("playback.backToLive")}
        </Button>
      ) : (<>
      <Segmented
        label={t("playback.speed")}
        options={SPEEDS}
        value={String(match.speed) as (typeof SPEEDS)[number]["value"]}
        onChange={(v) => playback.setSpeed(Number(v) as Speed)}
      />
      <Button variant="ghost" onClick={playback.restart}>
        {t("playback.restart")}
      </Button>
      </>)}
    </div>
  );
}
