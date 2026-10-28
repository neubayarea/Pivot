import { Link } from "react-router-dom";
import type { ViewerPrefs } from "@pivot/contracts";
import Brand from "./Brand";
import { useMatch } from "../data/match";
import { useT } from "../i18n";
import MatchPicker from "./MatchPicker";
import Segmented from "./Segmented";
import ViewerControls from "./ViewerControls";

// Each language names itself, so a viewer who cannot read the current one still finds theirs.
const LANGUAGES = [
  { value: "en", label: "EN" },
  { value: "zh", label: "中文", lang: "zh" },
  { value: "es", label: "ES" },
] as const;

type Props = {
  prefs: ViewerPrefs;
  onPrefsChange: (prefs: ViewerPrefs) => void;
};

// The site bar: brand, which match, the viewer's own controls (Ax68), language and the AI's work
// log. The score and the clock are in the match header under it (ScoreHeader, Ax59).
export default function TopBar({ prefs, onPrefsChange }: Props) {
  const { pivots } = useMatch();
  const t = useT();
  return (
    <header className="top">
      <Brand to="/" />
      <MatchPicker />
      <span className="sp" />
      <ViewerControls prefs={prefs} onPrefsChange={onPrefsChange} />
      <Segmented
        label={t("top.language")}
        options={LANGUAGES}
        value={prefs.language}
        onChange={(language) => onPrefsChange({ ...prefs, language })}
      />
      <Link to="/trace" className="btn top-trace">
        {t("top.trace", { n: pivots.length })}
      </Link>
    </header>
  );
}
