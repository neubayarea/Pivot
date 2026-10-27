// The match header (Ax59), Premier League match-page style: both teams in their colours, the big
// score, the clock and state, the goal scorers under each team, and the viewer's own controls
// (fan / analyst, ♥ team, ★ player) in plain sight instead of behind a Settings menu (#276).
// It sticks to the top of the window with the replay bar (App); on phones it keeps to one score row.
import { useEffect, type CSSProperties } from "react";
import type { MatchEvent, ViewerPrefs } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { goalFor } from "../data/keyMoments";
import { useMatch, type MatchView, type Side } from "../data/match";
import { useT, type T } from "../i18n";
import { PlayerPicker, TeamPicker, surname } from "./FocusPickers";
import Segmented from "./Segmented";
import Stamp from "./Stamp";

const STATUS_TONE = { live: "live", paused: "warn", finished: "ok", scheduled: "line" } as const;

const audiences = (t: T) => [
  { value: "fan", label: t("top.audience.fan") },
  { value: "analyst", label: t("top.audience.analyst") },
] as const;

type Props = {
  prefs: ViewerPrefs;
  onPrefsChange: (prefs: ViewerPrefs) => void;
};

/** One scorer per line, their goals in match order: "Moreau 12′, 67′ (pen)"; an own goal under the side it counts for. */
export function scorers(events: MatchEvent[], side: Side, playerName: MatchView["playerName"], t: T, at: (t: number) => string): string[] {
  const goals = events.filter((e) => goalFor(e) === side).sort((a, b) => a.t - b.t);
  const lines = new Map<string, string[]>();
  for (const e of goals) {
    const who = e.player_id ? surname(playerName(e.player_id)) : "";
    const minute = `${at(e.t)}′` + (e.type !== "shot" ? ` ${t("header.og")}` : e.play_pattern === "penalty" ? ` ${t("header.pen")}` : "");
    lines.set(who, [...(lines.get(who) ?? []), minute]);
  }
  return [...lines].map(([who, minutes]) => `${who} ${minutes.join(", ")}`.trim());
}

function TeamSide({ side, fav }: { side: Side; fav: boolean }) {
  const { teams, events, playerName } = useMatch();
  const t = useT();
  const { at } = useClock();
  const team = teams[side];
  const goals = scorers(events, side, playerName, t, at);
  return (
    <div className={`mh-team ${side}${fav ? " fav" : ""}`} style={{ "--tc": team.color } as CSSProperties}>
      <span className="mh-name" title={team.name}>
        <span className="mh-crest" aria-hidden="true" />
        <span className="tm-full">{team.name}</span>
        <span className="tm-short">{team.short_name}</span>
        {fav && <span className="mh-fav" role="img" aria-label={t("top.team.label")}>♥</span>}
      </span>
      {goals.length > 0 && (
        <ul className="mh-goals" aria-label={t("header.scorers", { team: team.name })}>
          {goals.map((g) => <li key={g}>{g}</li>)}
        </ul>
      )}
    </div>
  );
}

export default function ScoreHeader({ prefs, onPrefsChange }: Props) {
  const { match, teams, squads } = useMatch();
  const t = useT();

  // A player saved while watching another match is not in this one; the API would refuse him.
  const player = prefs.focus_player_id;
  const known = !player || squads.home.length + squads.away.length === 0
    || [...squads.home, ...squads.away].some((p) => p.player_id === player);
  useEffect(() => {
    if (!known) onPrefsChange({ ...prefs, focus_player_id: null });
  }, [known]);

  return (
    <section className="mh" aria-label={t("header.label")}>
      <div className="mh-score">
        <TeamSide side="home" fav={prefs.focus_team === "home"} />
        <div className="mh-mid">
          <span className="mh-sc num" role="img" aria-label={`${teams.home.name} ${match.score.home}, ${teams.away.name} ${match.score.away}`}>
            <span>{match.score.home}</span>
            <span className="mh-dash" aria-hidden="true">–</span>
            <span>{match.score.away}</span>
          </span>
          <span className="mh-state">
            {match.status !== "scheduled" && <span className="mh-clock num">{match.clockLabel}</span>}
            <Stamp tone={STATUS_TONE[match.status]}>{t(`status.${match.status}`)}</Stamp>
          </span>
        </div>
        <TeamSide side="away" fav={prefs.focus_team === "away"} />
      </div>
      <div className="mh-ctl" role="group" aria-label={t("header.controls")}>
        <span className="mh-lbl">{t("top.audience")}</span>
        <Segmented
          label={t("top.audience")}
          options={audiences(t)}
          value={prefs.audience}
          onChange={(audience) => onPrefsChange({ ...prefs, audience })}
        />
        <TeamPicker prefs={prefs} onPrefsChange={onPrefsChange} />
        <PlayerPicker prefs={prefs} onPrefsChange={onPrefsChange} />
      </div>
    </section>
  );
}
