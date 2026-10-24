import { Link } from "react-router-dom";
import type { ViewerPrefs } from "@pivot/contracts";
import { useMatch } from "../data/match";
import Segmented from "./Segmented";
import Stamp from "./Stamp";

const AUDIENCES = [
  { value: "analyst", label: "Analyst" },
  { value: "fan", label: "Fan" },
] as const;

const LANGUAGES = [
  { value: "en", label: "EN" },
  { value: "zh", label: "中文" },
  { value: "es", label: "ES" },
] as const;

const STATUS = {
  live: <Stamp tone="live">Live</Stamp>,
  paused: <Stamp tone="warn">Paused</Stamp>,
  finished: <Stamp tone="ok">Full time</Stamp>,
  scheduled: <Stamp tone="line">Pre-match</Stamp>,
};

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
      {STATUS[match.status]}
      <span className="sp" />
      <Segmented
        label="Viewing mode"
        options={AUDIENCES}
        value={prefs.audience}
        onChange={(audience) => onPrefsChange({ ...prefs, audience })}
      />
      {/* Team and player focus pickers: placeholders until C08. Labels hide on mid-width screens. */}
      <span className="pick" title={`Team: ${teams.home.short_name}`}>
        ♥ <em><span className="pick-label">{teams.home.short_name} </span>▾</em>
      </span>
      <span className="pick" title="Player: Moreau">
        ★ <em><span className="pick-label">Moreau </span>▾</em>
      </span>
      <Segmented
        label="Language"
        options={LANGUAGES}
        value={prefs.language}
        onChange={(language) => onPrefsChange({ ...prefs, language })}
      />
      <Link to="/trace" className="btn">
        Trace {pivots.length}
      </Link>
    </header>
  );
}
