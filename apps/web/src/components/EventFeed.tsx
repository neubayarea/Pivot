import type { MatchEvent } from "@pivot/contracts";
import { useMatch } from "../data/match";

const ROWS = 8;
const TICK = { success: " ✓", fail: " ✗" } as const;

export function describe(e: MatchEvent, name: (id: string | null) => string): string {
  const who = name(e.player_id);
  const tick = e.outcome ? TICK[e.outcome] : "";
  switch (e.type) {
    case "pass":
      if (e.pass_type === "corner") return `Corner · ${e.meta.side ?? ""} side`;
      return e.receiver_id ? `Pass · ${who} → ${name(e.receiver_id)}${tick}` : `Pass · ${who}${tick}`;
    case "shot":
      if (e.shot_outcome === "goal") return `GOAL · ${who}`;
      return `Shot · ${who} · xG ${e.xg?.toFixed(2)}`;
    case "card":
      return `${e.meta.card === "red" ? "Red" : "Yellow"} card · ${who}`;
    case "substitution":
      return e.substitution
        ? `Substitution · ${name(e.substitution.player_on_id)} on, ${name(e.substitution.player_off_id)} off`
        : "Substitution";
    case "tactical_shift":
      return `Tactical shift · ${e.meta.note ?? ""}`;
    case "kickoff":
      return "Kick-off";
    case "period_end":
      return e.period === 1 ? "Half time" : "Full time";
    default:
      return `${e.type[0].toUpperCase()}${e.type.slice(1).replace("_", " ")} · ${who}${tick}`;
  }
}

const KEY_TYPES = new Set<MatchEvent["type"]>(["card", "substitution", "tactical_shift", "period_end", "kickoff"]);

export default function EventFeed({ highlight }: { highlight: ReadonlySet<string> }) {
  const { events, teams, playerName } = useMatch();
  return (
    <div className="feed" aria-live="polite">
      {/* The newest rows, plus any older event picked as evidence in "Why it turned". */}
      {events.filter((e, i) => i < ROWS || highlight.has(e.event_id)).map((e) => {
        const key = KEY_TYPES.has(e.type) || e.shot_outcome === "goal";
        return (
          <div key={e.event_id} className={`${key ? "key" : ""}${highlight.has(e.event_id) ? " on" : ""}`}>
            <span className="t">{e.clock_label}</span>
            <span className={e.team === "home" ? "h" : "a"}>{teams[e.team].short_name}</span>
            <span>{describe(e, playerName)}</span>
          </div>
        );
      })}
    </div>
  );
}
