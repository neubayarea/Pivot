import { useMemo, useState } from "react";
import { fixtureMode, useMatch } from "../data/match";
import { useFrames } from "../data/live/frames";
import { useT } from "../i18n";
import Card from "./Card";
import { describe } from "./EventFeed";
import Pitch from "./Pitch";

// A shot stays drawn this many seconds after it was taken.
const SHOT_FOR = 3;
// The dots glide at least this long between frames, so fast replays still look like movement.
const MIN_STEP_MS = 250;

/**
 * S1 pitch board (C45): all 22 players and the ball at the match clock, one frame per second.
 * It has no timeline of its own: during a replay it follows the replay bar (Playback), so
 * dragging that bar moves the players too; on a match that is not being replayed it shows
 * where everyone stood at the current clock.
 */
export default function PitchBoard() {
  const { match, playback, squads, teams, events, playerName } = useMatch();
  const t = useT();
  // The fixture has no frames to fetch; neither has a page rendered with no browser (the tests).
  const [fixture] = useState(() => typeof window === "undefined" || fixtureMode());
  const now = Math.floor(match.clock);
  const { frame, missing } = useFrames(fixture ? null : match.match_id, now);

  const who = useMemo(() => {
    const map = new Map<string, { home: boolean; shirt: string }>();
    for (const side of ["home", "away"] as const) {
      for (const p of squads[side]) map.set(p.player_id, { home: side === "home", shirt: p.shirt === null ? "" : String(p.shirt) });
    }
    return (id: string) => map.get(id) ?? { home: id.startsWith("h"), shirt: "" };
  }, [squads]);

  const note = t("board.pitchNote", { team: teams.home.short_name });
  if (missing) {
    return (
      <Card title={t("board.pitch")} note={note}>
        <div className="empty-box muted">{t("board.pitchNone")}</div>
      </Card>
    );
  }

  // events are newest first: the latest one at or before the frame, and shots just taken.
  const latest = events.find((e) => e.t <= now);
  const shots = events.filter((e) => e.type === "shot" && e.location && e.t <= now && now - e.t <= SHOT_FOR);
  // One frame per second of play: at 1× that is a second between frames, faster replays less.
  const stepMs = Math.max(MIN_STEP_MS, 1000 / (playback?.playing ? match.speed : 1));
  return (
    <Card title={t("board.pitch")} note={note} className="pitch-board">
      {frame ? (
        <Pitch frame={frame} actions={shots} selected={null} who={who} stepMs={stepMs}
          label={t("detail.pitchLabel", { t: frame.t, n: frame.players.length })} />
      ) : (
        <div className="empty-box muted">{t("board.pitchLoading")}</div>
      )}
      <p className="pitch-cap">
        {latest && (
          <>
            <b>{latest.clock_label} · {teams[latest.team].short_name}</b> {describe(latest, playerName, t)}
          </>
        )}
        {!playback && <span className="muted">{latest && " · "}{t("board.pitchHint")}</span>}
      </p>
    </Card>
  );
}
