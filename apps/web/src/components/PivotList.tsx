import { Link } from "react-router-dom";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { useMatch } from "../data/match";
import Stamp from "./Stamp";

export function Severity({ level }: { level: Pivot["severity"] }) {
  return (
    <span className="sev" aria-label={`Severity ${level} of 3`}>
      {"●".repeat(level)}
      <i>{"●".repeat(3 - level)}</i>
    </span>
  );
}

export default function PivotList({ activeId }: { activeId: string | null }) {
  const { pivots, teams } = useMatch();
  if (!pivots.length) return <p className="muted">No pivots yet. Watching the momentum line.</p>;
  return (
    <div>
      {pivots.map((p) =>
        p.status === "pending" ? (
          <div key={p.pivot_id} className="pv wait">
            <span className="m">{p.minute}′</span>
            <span className="tt">Checking a momentum swing…</span>
            <span className="meta">
              <Stamp tone="line">Analysing…</Stamp>
            </span>
          </div>
        ) : (
          <Link key={p.pivot_id} to={`/pivot/${p.pivot_id}`} className={`pv${p.pivot_id === activeId ? " active" : ""}`}>
            <span className="m">{p.minute}′</span>
            <span className="tt">{p.narrative?.headline}</span>
            <span className="meta">
              <Severity level={p.severity} />
              <Stamp tone="ok">Verified ✓</Stamp>
            </span>
            <span className="to">Momentum → {teams[p.direction].name}</span>
          </Link>
        ),
      )}
    </div>
  );
}
