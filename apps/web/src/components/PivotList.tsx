import { Link } from "react-router-dom";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { useMatch, type MatchView } from "../data/match";
import Stamp from "./Stamp";

/** How far the checking pipeline got: verified by the AI, or the template fallback when it timed out. */
export function PivotStamp({ status }: { status: Pivot["status"] }) {
  if (status === "pending") return <Stamp tone="line">Analysing…</Stamp>;
  if (status === "degraded") return <Stamp tone="warn">Auto summary</Stamp>;
  if (status === "rejected") return <Stamp tone="bad">Not a pivot</Stamp>;
  return <Stamp tone="ok">Verified ✓</Stamp>;
}

/** A degraded pivot can arrive without a narrative; it still needs a line in the list. */
export const pivotHeadline = (p: Pivot, teams: MatchView["teams"]) =>
  p.narrative?.headline ?? `Momentum swung to ${teams[p.direction].name}`;

export function Severity({ level }: { level: Pivot["severity"] }) {
  return (
    <span className="sev" aria-label={`Severity ${level} of 3`}>
      {"●".repeat(level)}
      <i>{"●".repeat(3 - level)}</i>
    </span>
  );
}

export default function PivotList({ activeId }: { activeId: string | null }) {
  const { teams, pivots: all } = useMatch();
  // The checker ruled these out; the live feed already drops them, the fixture never has any.
  const pivots = all.filter((p) => p.status !== "rejected");
  if (!pivots.length) return <p className="muted">No pivots yet. Watching the momentum line.</p>;
  return (
    <div>
      {pivots.map((p) =>
        p.status === "pending" ? (
          <div key={p.pivot_id} className="pv wait">
            <span className="m">{p.minute}′</span>
            <span className="tt">Checking a momentum swing…</span>
            <span className="meta">
              <PivotStamp status="pending" />
            </span>
          </div>
        ) : (
          <Link key={p.pivot_id} to={`/pivot/${p.pivot_id}`} className={`pv${p.pivot_id === activeId ? " active" : ""}`}>
            <span className="m">{p.minute}′</span>
            <span className="tt">{pivotHeadline(p, teams)}</span>
            <span className="meta">
              <Severity level={p.severity} />
              <PivotStamp status={p.status} />
            </span>
            <span className="to">Momentum → {teams[p.direction].name}</span>
          </Link>
        ),
      )}
    </div>
  );
}
