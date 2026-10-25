import type { MatchEvent } from "@pivot/contracts";
import { involves, isRedCard, useMatch } from "../data/match";
import { isMessageKey, usePrefs, type T } from "../i18n";

const ROWS = 8;
const TICK = { success: " ✓", fail: " ✗" } as const;

export function describe(e: MatchEvent, name: (id: string | null) => string, t: T): string {
  const who = name(e.player_id);
  const tick = e.outcome ? TICK[e.outcome] : "";
  switch (e.type) {
    case "pass": {
      const side = e.meta.side;
      if (e.pass_type === "corner") {
        return t("event.corner", { side: side === "left" || side === "right" ? t(`event.side.${side}`) : "" });
      }
      return e.receiver_id
        ? t("event.pass", { who, to: name(e.receiver_id), tick })
        : t("event.passSolo", { who, tick });
    }
    case "shot":
      if (e.shot_outcome === "goal") return t("event.goal", { who });
      if (e.shot_outcome === "disallowed") return t("event.goalDisallowed", { who });
      return t("event.shot", { who, xg: e.xg?.toFixed(2) ?? "" });
    case "card":
      return t(isRedCard(e) ? "event.red" : "event.yellow", { who });
    case "substitution":
      return e.substitution
        ? t("event.sub", { on: name(e.substitution.player_on_id), off: name(e.substitution.player_off_id) })
        : t("event.subBare");
    case "tactical_shift":
      return t("event.shift", { note: String(e.meta.note ?? "") });
    case "kickoff":
      return t("event.kickoff");
    case "period_end":
      return t(e.period === 1 ? "event.halfTime" : "event.fullTime");
    default:
    {
      const key = `event.type.${e.type}`;
      const type = isMessageKey(key) ? t(key) : e.type[0].toUpperCase() + e.type.slice(1).replaceAll("_", " ");
      return t("event.other", { type, who, tick });
    }
  }
}

const KEY_TYPES = new Set<MatchEvent["type"]>(["card", "substitution", "tactical_shift", "period_end", "kickoff"]);

export default function EventFeed({ highlight }: { highlight: ReadonlySet<string> }) {
  const { events, teams, playerName } = useMatch();
  const { prefs, t } = usePrefs();
  if (!events.length) return <p className="muted">{t("feed.empty")}</p>;
  return (
    <div className="feed" aria-live="polite">
      {/* The newest rows, plus any older event picked as evidence in "Why it turned". */}
      {events.filter((e, i) => i < ROWS || highlight.has(e.event_id)).map((e) => {
        const key = KEY_TYPES.has(e.type) || e.shot_outcome === "goal" || e.shot_outcome === "disallowed";
        return (
          <div key={e.event_id}
            className={`${key ? "key" : ""}${highlight.has(e.event_id) ? " on" : ""}${involves(e, prefs.focus_player_id) ? " mine" : ""}`}>
            <span className="t">{e.clock_label}</span>
            <span className={e.team === "home" ? "h" : "a"}>{teams[e.team].short_name}</span>
            <span>{describe(e, playerName, t)}</span>
          </div>
        );
      })}
    </div>
  );
}
