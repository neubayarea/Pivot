import { useEffect, useMemo, useState } from "react";
import { fixtureMode, useMatch } from "../data/match";
import { useFrames } from "../data/live/frames";
import { useT } from "../i18n";
import Card from "./Card";
import { describe } from "./EventFeed";
import Pitch from "./Pitch";
import Scrubber from "./Scrubber";

// Without a replay running, the board plays on its own: one second of play every 250 ms, as on S2.
const OWN_STEP_MS = 250;
// A shot stays drawn this many seconds after it was taken.
const SHOT_FOR = 3;

/**
 * S1 pitch board (C45): all 22 players and the ball, one frame per second of the match.
 * During Start demo it follows the replay clock and dragging seeks the replay; otherwise it has
 * its own clock, from kick-off to where the match is now.
 */
export default function PitchBoard() {
  const { match, playback, squads, teams, pivots, events, playerName } = useMatch();
  const t = useT();
  // The fixture has no frames to fetch; neither has a page rendered with no browser (the tests).
  const [fixture] = useState(() => typeof window === "undefined" || fixtureMode());
  const end = playback ? playback.end : match.clock;
  const [own, setOwn] = useState(0);
  const [ownPlaying, setOwnPlaying] = useState(false);
  const now = Math.min(end, Math.floor(playback ? match.clock : own));
  const { frame, missing } = useFrames(fixture ? null : match.match_id, now);

  useEffect(() => {
    if (playback || !ownPlaying) return;
    const h = setInterval(() => setOwn((s) => Math.min(end, s + 1)), OWN_STEP_MS);
    return () => clearInterval(h);
  }, [playback, ownPlaying, end]);
  useEffect(() => {
    if (!playback && own >= end) setOwnPlaying(false);
  }, [playback, own, end]);

  const who = useMemo(() => {
    const map = new Map<string, { home: boolean; shirt: string }>();
    for (const side of ["home", "away"] as const) {
      for (const p of squads[side]) map.set(p.player_id, { home: side === "home", shirt: p.shirt === null ? "" : String(p.shirt) });
    }
    return (id: string) => map.get(id) ?? { home: id.startsWith("h"), shirt: "" };
  }, [squads]);

  const goals = useMemo(() => events.filter((e) => e.type === "shot" && e.shot_outcome === "goal"), [events]);
  const playing = playback ? playback.playing : ownPlaying;
  const seek = (s: number) => (playback ? playback.seek(s) : setOwn(s));
  const play = (on: boolean) => {
    if (on && now >= end) seek(0);              // play again from kick-off
    if (playback) playback.setPlaying(on);
    else setOwnPlaying(on);
  };

  const note = t("board.pitchNote", { team: teams.home.short_name });
  if (missing || end <= 0) {
    return (
      <Card title={t("board.pitch")} note={note}>
        <div className="empty-box muted">{t("board.pitchNone")}</div>
      </Card>
    );
  }

  // events are newest first: the latest one at or before the frame, and shots just taken.
  const latest = events.find((e) => e.t <= now);
  const shots = events.filter((e) => e.type === "shot" && e.location && e.t <= now && now - e.t <= SHOT_FOR);
  const speed = playback ? match.speed : 1000 / OWN_STEP_MS;
  return (
    <Card title={t("board.pitch")} note={note} className="pitch-board">
      {frame ? (
        <Pitch frame={frame} actions={shots} selected={null} who={who} stepMs={Math.max(OWN_STEP_MS, 1000 / speed)}
          label={t("detail.pitchLabel", { t: frame.t, n: frame.players.length })} />
      ) : (
        <div className="empty-box muted pitch-wait">{t("board.pitchLoading")}</div>
      )}
      <Scrubber window={[0, end]} t={now} onChange={seek} playing={playing} onPlayingChange={play}
        pivotMinutes={[...new Set(pivots.map((p) => p.minute))]} marks={goals.map((e) => ({ t: e.t, on: false }))} />
      <p className="pitch-cap">
        {latest ? (
          <>
            <b>{latest.clock_label} · {teams[latest.team].short_name}</b> {describe(latest, playerName, t)}
          </>
        ) : (
          <span className="muted">{t("board.pitchHint")}</span>
        )}
      </p>
    </Card>
  );
}
