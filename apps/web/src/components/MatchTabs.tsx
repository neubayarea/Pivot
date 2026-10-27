// The tabs under the match header (Ax59). Each is a real link, so it can be opened in a new tab,
// shared, or jumped to in a recording; the match and replay in the link stay as they are.
// C11: the full tabs pattern for the keyboard. Only the open tab is in the Tab order; the arrow
// keys, Home and End move to another tab and open it.
import { useRef, type KeyboardEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useMatch } from "../data/match";
import { TABS, tabSearch, type MatchTab } from "../data/tab";
import { useT } from "../i18n";

export default function MatchTabs({ tab }: { tab: MatchTab }) {
  const { search } = useLocation();
  const navigate = useNavigate();
  const t = useT();
  // C13: the replay is "Live" while the match is being played.
  const live = ["live", "paused"].includes(useMatch().match.status);
  const list = useRef<HTMLDivElement>(null);
  const move = (e: KeyboardEvent) => {
    const i = TABS.indexOf(tab);
    const to = ({ ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: TABS.length - 1 } as Record<string, number>)[e.key];
    if (to === undefined) return;
    e.preventDefault();
    const next = TABS[(to + TABS.length) % TABS.length];
    navigate({ search: tabSearch(search, next) }, { preventScrollReset: true });
    requestAnimationFrame(() => list.current?.querySelector<HTMLElement>(`#tab-${next}`)?.focus());
  };
  return (
    <nav className="tabs" aria-label={t("tabs.label")}>
      <div role="tablist" ref={list} onKeyDown={move}>
        {TABS.map((id) => (
          <Link key={id} id={`tab-${id}`} role="tab" aria-selected={id === tab} aria-controls={id === tab ? `panel-${id}` : undefined}
            tabIndex={id === tab ? 0 : -1} to={{ search: tabSearch(search, id) }} preventScrollReset>
            {t(id === "replay" && live ? "tabs.live" : `tabs.${id}`)}
          </Link>
        ))}
      </div>
    </nav>
  );
}
