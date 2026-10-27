// The tabs under the match header (Ax59). Each is a real link, so it can be opened in a new tab,
// shared, or jumped to in a recording; the match and replay in the link stay as they are.
import { Link, useLocation } from "react-router-dom";
import { TABS, tabSearch, type MatchTab } from "../data/tab";
import { useT } from "../i18n";

export default function MatchTabs({ tab }: { tab: MatchTab }) {
  const { search } = useLocation();
  const t = useT();
  return (
    <nav className="tabs" aria-label={t("tabs.label")}>
      <div role="tablist">
        {TABS.map((id) => (
          <Link key={id} id={`tab-${id}`} role="tab" aria-selected={id === tab} aria-controls={`panel-${id}`}
            to={{ search: tabSearch(search, id) }} preventScrollReset>
            {t(`tabs.${id}`)}
          </Link>
        ))}
      </div>
    </nav>
  );
}
