// The match header (Ax59), Premier League match-page style: both teams in their colours, the big
// score, the clock and state, and the goal scorers under each team. The viewer's own controls
// (fan / analyst, ♥ team, ★ player) are in the site bar above it (ViewerControls, Ax68).
// It sticks to the top of the window with the replay bar (App); on phones it keeps to one score row.
// Scrolled past, it folds into a slim bar of names, score and clock (Ax66, data/headerFold.ts); a
// button on each opens or folds it by hand.
// Ax69: a ♥ beside each team's name, open or slim, picks it as the viewer's team and lets it go
// again; under the open header a "Following: X ✕" chip while a ★ player is followed.
import { useId, useLayoutEffect, useRef, type CSSProperties, type RefObject } from "react";
import type { MatchEvent, ViewerPrefs } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { goalFor } from "../data/keyMoments";
import { useMatch, type MatchView, type Side } from "../data/match";
import { useT, type T } from "../i18n";
import { surname } from "./FocusPickers";
import FollowTeam, { FollowingChip } from "./FollowTeam";
import Stamp from "./Stamp";

const STATUS_TONE = { live: "live", paused: "warn", finished: "ok", scheduled: "line" } as const;

type Props = {
  prefs: ViewerPrefs;
  /** Folding with the scroll (App); without it the header always shows in full. */
  fold?: { slim: boolean; toggle: () => void };
};

const Chevron = () => (
  <svg className="mh-chev" viewBox="0 0 16 16" width={16} height={16} aria-hidden="true">
    <path d="M3.5 6l4.5 4.5L12.5 6" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

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
        <FollowTeam side={side} />
      </span>
      {goals.length > 0 && (
        <ul className="mh-goals" aria-label={t("header.scorers", { team: team.name })}>
          {goals.map((g) => <li key={g}>{g}</li>)}
        </ul>
      )}
    </div>
  );
}

/** The folded header: each team's kit chip and name, the score and the clock, and the button that opens it. */
function SlimBar({ favTeam, controls, onExpand, button, track }: {
  favTeam: ViewerPrefs["focus_team"];
  controls: string;
  onExpand: () => void;
  button: RefObject<HTMLButtonElement | null>;
  track: { onFocus: () => void; onBlur: () => void };
}) {
  const { match, teams } = useMatch();
  const t = useT();
  const side = (s: Side) => (
    <span className={`mh-bar-team ${s}${favTeam === s ? " fav" : ""}`} style={{ "--tc": teams[s].color } as CSSProperties} title={teams[s].name}>
      <span className="mh-chip" aria-hidden="true" />
      <span className="tm-full">{teams[s].name}</span>
      <span className="tm-short">{teams[s].short_name}</span>
      <FollowTeam side={s} />
    </span>
  );
  return (
    <div className="mh-bar">
      {side("home")}
      <span className="mh-bar-mid">
        <span className="mh-bar-sc num" role="img" aria-label={`${teams.home.name} ${match.score.home}, ${teams.away.name} ${match.score.away}`}>
          <span>{match.score.home}</span>
          <span className="mh-dash" aria-hidden="true">–</span>
          <span>{match.score.away}</span>
        </span>
        {match.status !== "scheduled" && <span className="mh-clock num">{match.clockLabel}</span>}
        <Stamp tone={STATUS_TONE[match.status]}>{t(`status.${match.status}`)}</Stamp>
      </span>
      {side("away")}
      <button ref={button} type="button" className="mh-toggle open" aria-expanded={false} aria-controls={controls}
        aria-label={t("header.expand.label")} title={t("header.expand.label")} onClick={onExpand} {...track}>
        <span className="mh-toggle-txt">{t("header.expand")}</span>
        <Chevron />
      </button>
    </div>
  );
}

export default function ScoreHeader({ prefs, fold }: Props) {
  const { match, teams } = useMatch();
  const t = useT();
  const id = useId();
  const slim = !!fold?.slim;

  // The button pressed goes away with the layout it was in; the one that undoes it takes the focus
  // (without scrolling: Chrome would scroll a stuck header back to where it sits unstuck).
  // The same when the scroll switches it while the button has the focus.
  const button = useRef<HTMLButtonElement>(null);
  const pressed = useRef(false);
  const focused = useRef(false);
  const press = () => {
    pressed.current = true;
    fold?.toggle();
  };
  const track = { onFocus: () => void (focused.current = true), onBlur: () => void (focused.current = false) };
  useLayoutEffect(() => {
    const lost = focused.current && (document.activeElement === document.body || !document.activeElement);
    if (pressed.current || lost) button.current?.focus({ preventScroll: true });
    pressed.current = false;
  }, [slim]);


  if (slim) {
    return (
      <section className="mh slim" id={id} aria-label={t("header.label")}>
        <SlimBar favTeam={prefs.focus_team} controls={id} onExpand={press} button={button} track={track} />
      </section>
    );
  }

  return (
    <section className="mh" id={id} aria-label={t("header.label")}>
      {fold && (
        <button ref={button} type="button" className="mh-toggle shut" aria-expanded={true} aria-controls={id}
          aria-label={t("header.collapse.label")} title={t("header.collapse.label")} onClick={press} {...track}>
          <Chevron />
        </button>
      )}
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
      <FollowingChip />
    </section>
  );
}
