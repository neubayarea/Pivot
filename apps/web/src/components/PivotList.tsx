import { Link } from "react-router-dom";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { useMatch, type MatchView } from "../data/match";
import { narrativeLang, useT, type T } from "../i18n";
import LangTag from "./LangTag";
import Stamp from "./Stamp";

/** How far the checking pipeline got: verified by the AI, or the template fallback when it timed out. */
export function PivotStamp({ status }: { status: Pivot["status"] }) {
  const t = useT();
  if (status === "pending") return <Stamp tone="line">{t("stamp.pending")}</Stamp>;
  if (status === "degraded") return <Stamp tone="warn">{t("stamp.degraded")}</Stamp>;
  if (status === "rejected") return <Stamp tone="bad">{t("stamp.rejected")}</Stamp>;
  return <Stamp tone="ok">{t("stamp.verified")}</Stamp>;
}

/** A degraded pivot can arrive without a narrative; it still needs a line in the list. */
export const pivotHeadline = (p: Pivot, teams: MatchView["teams"], t: T) =>
  p.narrative?.headline ?? t("pivot.fallbackHeadline", { team: teams[p.direction].name });

export function Severity({ level }: { level: Pivot["severity"] }) {
  const t = useT();
  return (
    <span className="sev" role="img" aria-label={t("pivot.severity", { n: level })}>
      {"●".repeat(level)}
      <i>{"●".repeat(3 - level)}</i>
    </span>
  );
}

export default function PivotList({ activeId }: { activeId: string | null }) {
  const { teams, pivots: all } = useMatch();
  const t = useT();
  const { minute } = useClock();
  // The checker ruled these out; the live feed already drops them, the fixture never has any.
  const pivots = all.filter((p) => p.status !== "rejected");
  if (!pivots.length) return <p className="muted">{t("pivots.empty")}</p>;
  return (
    <div>
      {pivots.map((p) =>
        p.status === "pending" ? (
          <div key={p.pivot_id} className="pv wait">
            <span className="m">{minute(p.minute)}′</span>
            <span className="tt">{t("pivots.checking")}</span>
            <span className="meta">
              <PivotStamp status="pending" />
            </span>
          </div>
        ) : (
          <Link key={p.pivot_id} to={`/pivot/${p.pivot_id}`} className={`pv to-${p.direction}${p.pivot_id === activeId ? " active" : ""}`}>
            <span className="m">{minute(p.minute)}′</span>
            <span className="tt">{pivotHeadline(p, teams, t)} <LangTag lang={narrativeLang(p.narrative)} /></span>
            <span className="meta">
              <Severity level={p.severity} />
              <PivotStamp status={p.status} />
            </span>
            <span className="to">{t("pivot.momentumTo", { team: teams[p.direction].name })}</span>
          </Link>
        ),
      )}
    </div>
  );
}
