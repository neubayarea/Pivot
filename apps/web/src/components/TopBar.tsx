import { Link } from "react-router-dom";
import type { Score, ViewerPrefs } from "@pivot/contracts";
import Button from "./Button";
import Segmented from "./Segmented";
import Stamp from "./Stamp";

// Static placeholders until C02 wires the live match feed.
const SCORE: Pick<Score, "home" | "away"> = { home: 1, away: 1 };
const HOME = "Harbour City";
const AWAY = "Northvale Rovers";
const CLOCK = "74:12";

const AUDIENCES = [
  { value: "analyst", label: "Analyst" },
  { value: "fan", label: "Fan" },
] as const;

const LANGUAGES = [
  { value: "en", label: "EN" },
  { value: "zh", label: "中文" },
  { value: "es", label: "ES" },
] as const;

type Props = {
  prefs: ViewerPrefs;
  onPrefsChange: (prefs: ViewerPrefs) => void;
};

export default function TopBar({ prefs, onPrefsChange }: Props) {
  return (
    <header className="top">
      <Link to="/" className="brand">
        Pivot
      </Link>
      <span className="score">
        <span className="tm">{HOME}</span>
        <span className="sc num">{SCORE.home}</span>
        <span className="sc num">{SCORE.away}</span>
        <span className="tm">{AWAY}</span>
      </span>
      <span className="clock">{CLOCK}</span>
      <Stamp tone="live">Live</Stamp>
      <span className="sp" />
      <Segmented
        label="Viewing mode"
        options={AUDIENCES}
        value={prefs.audience}
        onChange={(audience) => onPrefsChange({ ...prefs, audience })}
      />
      <Segmented
        label="Language"
        options={LANGUAGES}
        value={prefs.language}
        onChange={(language) => onPrefsChange({ ...prefs, language })}
      />
      <Button>Trace</Button>
    </header>
  );
}
