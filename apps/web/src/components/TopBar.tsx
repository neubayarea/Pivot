import { Link } from "react-router-dom";
import type { ViewerPrefs } from "@pivot/contracts";
import { useMatch } from "../data/match";
import { useT, type T } from "../i18n";
import Button from "./Button";
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

// Both names render; CSS swaps to the three-letter code when the bar is short of room.
function TeamName({ name, short }: { name: string; short: string }) {
  return (
    <span className="tm">
      <span className="tm-full">{name}</span>
      <span className="tm-short">{short}</span>
    </span>
  );
}

export default function TopBar({ prefs, onPrefsChange }: Props) {
  const { match, teams, pivots } = useMatch();
  const t = useT();

  return (
    <header className="top">
      <Link to="/" className="brand">
        Pivot
      </Link>
      <span className="score" aria-label={`${teams.home.name} ${match.score.home}, ${teams.away.name} ${match.score.away}`}>
        <TeamName name={teams.home.name} short={teams.home.short_name} />
        <span className="sc num">{match.score.home}</span>
        <span className="sc num">{match.score.away}</span>
        <TeamName name={teams.away.name} short={teams.away.short_name} />
      </span>
      <span className="clock">{match.clockLabel}</span>
      <Stamp tone={STATUS_TONE[match.status]}>{t(`status.${match.status}`)}</Stamp>
      <span className="sp" />
      <Segmented
        label={t("top.audience")}
        options={audiences(t)}
        value={prefs.audience}
        onChange={(audience) => onPrefsChange({ ...prefs, audience })}
      />
      {/* Team and player focus pickers: placeholders until C08. Labels hide on mid-width screens. */}
      <span className="pick" title={t("top.team", { team: teams.home.short_name })}>
        ♥ <em><span className="pick-label">{teams.home.short_name} </span>▾</em>
      </span>
      <span className="pick" title={t("top.player", { player: "Moreau" })}>
        ★ <em><span className="pick-label">Moreau </span>▾</em>
      </span>
      <Segmented
        label={t("top.language")}
        options={LANGUAGES}
        value={prefs.language}
        onChange={(language) => onPrefsChange({ ...prefs, language })}
      />
      <Button>{t("top.trace", { n: pivots.length })}</Button>
    </header>
  );
}
