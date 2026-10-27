// The tabs under the match header (Ax59). Each is a real link, so it can be opened in a new tab,
// shared, or jumped to in a recording; the match and replay in the link stay as they are.
// C11: the full tabs pattern for the keyboard. Only the open tab is in the Tab order; the arrow
// keys, Home and End move to another tab and open it.
import { useRef, type KeyboardEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useMatch } from "../data/match";
import { TABS, tabOpen, tabSearch, type MatchTab } from "../data/tab";
import { useT } from "../i18n";

export default function MatchTabs({ tab }: { tab: MatchTab }) {
  const { search } = useLocation();
  const navigate = useNavigate();
  const t = useT();
  // C13: the replay is "Live" while the match is being played.
  const { status, match_id } = useMatch().match;
  const live = ["live", "paused"].includes(status);
  // C14: before kick-off only the preview and the line-ups have anything to show.
  const open = TABS.filter((id) => tabOpen(id, status, match_id));
  const list = useRef<HTMLDivElement>(null);
  const move = (e: KeyboardEvent) => {
    const i = open.indexOf(tab);
    const to = ({ ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: open.length - 1 } as Record<string, number>)[e.key];
    if (to === undefined) return;
    e.preventDefault();
    const next = open[(to + open.length) % open.length];
    navigate({ search: tabSearch(search, next) }, { preventScrollReset: true });
    requestAnimationFrame(() => list.current?.querySelector<HTMLElement>(`#tab-${next}`)?.focus());
  };
  return (
    <nav className="tabs" aria-label={t("tabs.label")}>
      <div role="tablist" ref={list} onKeyDown={move}>
        {TABS.map((id) => !tabOpen(id, status, match_id) ? (
          <span key={id} id={`tab-${id}`} role="tab" aria-selected={false} aria-disabled="true" className="tab-off"
            title={t("tabs.notYet")}>
            {t(`tabs.${id}`)}
          </span>
        ) : (
          <Link key={id} id={`tab-${id}`} role="tab" aria-selected={id === tab} aria-controls={id === tab ? `panel-${id}` : undefined}
            tabIndex={id === tab ? 0 : -1} to={{ search: tabSearch(search, id) }} preventScrollReset>
            {t(id === "replay" && live ? "tabs.live" : `tabs.${id}`)}
          </Link>
        ))}
      </div>
    </nav>
  );
}
