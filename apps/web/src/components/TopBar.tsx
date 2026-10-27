import { Link } from "react-router-dom";
import type { ViewerPrefs } from "@pivot/contracts";
import { useMatch } from "../data/match";
import { useT } from "../i18n";
import MatchPicker from "./MatchPicker";
import Segmented from "./Segmented";

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

// The site bar: brand, which match, language and the AI's work log. The score, the clock and the
// viewer's own controls moved to the match header under it (ScoreHeader, Ax59).
export default function TopBar({ prefs, onPrefsChange }: Props) {
  const { pivots } = useMatch();
  const t = useT();
  return (
    <header className="top">
      <Link to="/" className="brand">
        Pivot
      </Link>
      <MatchPicker />
      <span className="sp" />
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
