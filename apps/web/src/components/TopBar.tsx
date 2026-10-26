import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import type { ViewerPrefs } from "@pivot/contracts";
import { useMatch } from "../data/match";
import { useT, type T } from "../i18n";
import MatchPicker from "./MatchPicker";
import { PlayerPicker, TeamPicker } from "./FocusPickers";
import Segmented from "./Segmented";
import Stamp from "./Stamp";

const audiences = (t: T) => [
  { value: "analyst", label: t("top.audience.analyst") },
  { value: "fan", label: t("top.audience.fan") },
] as const;

// Each language names itself, so a viewer who cannot read the current one still finds theirs.
const LANGUAGES = [
  { value: "en", label: "EN" },
  { value: "zh", label: "中文" },
  { value: "es", label: "ES" },
] as const;

const STATUS_TONE = { live: "live", paused: "warn", finished: "ok", scheduled: "line" } as const;

type Props = {
  prefs: ViewerPrefs;
  onPrefsChange: (prefs: ViewerPrefs) => void;
};

// Both names render; CSS swaps to the three-letter code when the bar is short of room. The viewer's
// own team gets a ♥ and its colour underneath.
function TeamName({ name, short, fav }: { name: string; short: string; fav: boolean }) {
  return (
    <span className={`tm${fav ? " fav" : ""}`}>
      <span className="tm-full">{name}</span>
      <span className="tm-short">{short}</span>
    </span>
  );
}

export default function TopBar({ prefs, onPrefsChange }: Props) {
  const { match, teams, pivots, squads } = useMatch();
  const t = useT();
  const fav = prefs.focus_team;

  // A player saved while watching another match is not in this one; the API would refuse him.
  const player = prefs.focus_player_id;
  const known = !player || squads.home.length + squads.away.length === 0
    || [...squads.home, ...squads.away].some((p) => p.player_id === player);
  useEffect(() => {
    if (!known) onPrefsChange({ ...prefs, focus_player_id: null });
  }, [known]);

  // The settings menu closes on a click elsewhere or Escape, like the player picker.
  const menu = useRef<HTMLDetailsElement>(null);
  const close = () => menu.current?.removeAttribute("open");
  useEffect(() => {
    const away = (e: Event) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !menu.current?.contains(e.target as Node)) close();
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", away);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", away);
    };
  }, []);

  return (
    <header className="top">
      <Link to="/" className="brand">
        Pivot
      </Link>
      <span className="score" aria-label={`${teams.home.name} ${match.score.home}, ${teams.away.name} ${match.score.away}`}>
        <TeamName name={teams.home.name} short={teams.home.short_name} fav={fav === "home"} />
        <span className="sc num">{match.score.home}</span>
        <span className="sc num">{match.score.away}</span>
        <TeamName name={teams.away.name} short={teams.away.short_name} fav={fav === "away"} />
      </span>
      <span className="clock">{match.clockLabel}</span>
      <Stamp tone={STATUS_TONE[match.status]}>{t(`status.${match.status}`)}</Stamp>
      <MatchPicker />
      <span className="sp" />
      <Segmented
        label={t("top.language")}
        options={LANGUAGES}
        value={prefs.language}
        onChange={(language) => onPrefsChange({ ...prefs, language })}
      />
      {/* Everything else a viewer can set lives behind one button, so the bar keeps to the match. */}
      <details className="settings" ref={menu}>
        <summary className="btn">{t("top.settings")}{(fav || player) && <span className="dot" aria-label={t("top.settingsSet")} />}</summary>
        <div className="settings-pop">
          <span className="lbl">{t("top.audience")}</span>
          <Segmented
            label={t("top.audience")}
            options={audiences(t)}
            value={prefs.audience}
            onChange={(audience) => onPrefsChange({ ...prefs, audience })}
          />
          <span className="lbl">{t("top.team.label")}</span>
          <TeamPicker prefs={prefs} onPrefsChange={onPrefsChange} />
          <span className="lbl">{t("top.player.label")}</span>
          <PlayerPicker prefs={prefs} onPrefsChange={onPrefsChange} />
          <Link to="/trace" className="btn" onClick={close}>
            {t("top.trace", { n: pivots.length })}
          </Link>
        </div>
      </details>
    </header>
  );
}
