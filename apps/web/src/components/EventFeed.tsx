import { useEffect, useMemo, useRef, useState } from "react";
import type { MatchEvent } from "@pivot/contracts";
import { involves, isRedCard, useMatch } from "../data/match";
import { isMessageKey, usePrefs, type T } from "../i18n";

// Enough to scroll back through a good stretch of the match without drawing every pass of it.
const ROWS = 200;
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

// C16 (#366): what an analyst can filter the feed by. A fan sees only the big moments.
export const FEED_KINDS = ["shots", "setpieces", "fouls", "subs", "pivots"] as const;
export type FeedKind = (typeof FEED_KINDS)[number];
const SET_PASS = new Set(["corner", "free_kick", "throw_in"]);
const SET_SHOT = new Set(["corner", "free_kick", "penalty"]);

export function feedKind(e: MatchEvent, kind: FeedKind, turning: ReadonlySet<string>): boolean {
  switch (kind) {
    case "shots": return e.type === "shot";
    case "setpieces": return SET_PASS.has(e.pass_type ?? "") || (e.type === "shot" && SET_SHOT.has(e.play_pattern ?? ""));
    case "fouls": return e.type === "foul" || e.type === "card";
    case "subs": return e.type === "substitution";
    case "pivots": return turning.has(e.event_id);
  }
}

/** The fan's feed: goals, red cards, substitutions, the events that set a turning point off, and the whistles. */
export function bigMoment(e: MatchEvent, turning: ReadonlySet<string>): boolean {
  return e.shot_outcome === "goal" || isRedCard(e) || e.type === "substitution" || e.type === "kickoff" || e.type === "period_end" || turning.has(e.event_id);
}

export default function EventFeed({ highlight }: { highlight: ReadonlySet<string> }) {
  const { events, teams, pivots, playerName } = useMatch();
  const { prefs, t } = usePrefs();
  const fan = prefs.audience === "fan";
  const [kinds, setKinds] = useState<ReadonlySet<FeedKind>>(new Set());
  const turning = useMemo(() => new Set(pivots.flatMap((p) => p.trigger_event_ids)), [pivots]);
  const shown = events.filter((e) => (fan ? bigMoment(e, turning) : !kinds.size || [...kinds].some((k) => feedKind(e, k, turning))));
  const flip = (k: FeedKind) => setKinds((was) => {
    const next = new Set(was);
    if (!next.delete(k)) next.add(k);
    return next;
  });
  // Newest first, so following the replay means staying at the top; scrolling down to read stops that until scrolled back.
  const box = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const newest = events[0]?.event_id;
  useEffect(() => {
    if (follow.current && box.current) box.current.scrollTop = 0;
  }, [newest]);
  if (!events.length) return <p className="muted">{t("feed.empty")}</p>;
  return (
    <>
    {fan ? <p className="muted feed-note">{t("feed.fanNote")}</p> : (
      <div className="feed-kinds" role="group" aria-label={t("feed.filter")}>
        <button type="button" className="chip" aria-pressed={!kinds.size} onClick={() => setKinds(new Set())}>{t("feed.all")}</button>
        {FEED_KINDS.map((k) => (
          <button key={k} type="button" className="chip" aria-pressed={kinds.has(k)} onClick={() => flip(k)}>{t(`feed.k.${k}`)}</button>
        ))}
      </div>
    )}
    {/* C11: no aria-live here; at replay speed it would read out every row. New pivots have their own alert. */}
    <div className="feed" ref={box} onScroll={(e) => (follow.current = e.currentTarget.scrollTop < 24)}>
      {!shown.length && <p className="muted">{t("feed.none")}</p>}
      {/* The newest rows, plus any older event picked as evidence in "Why it turned". */}
      {shown.filter((e, i) => i < ROWS || highlight.has(e.event_id)).map((e) => {
        const key = KEY_TYPES.has(e.type) || e.shot_outcome === "goal" || e.shot_outcome === "disallowed";
        return (
          <div key={e.event_id}
            className={`${key ? "key" : ""}${highlight.has(e.event_id) ? " on" : ""}${involves(e, prefs.focus_player_id) ? " mine" : ""}`}>
            <span className="t">{e.clock_label.replace(/'/g, "′")}</span>
            <span className={e.team === "home" ? "h" : "a"}>{teams[e.team].short_name}</span>
            <span>{describe(e, playerName, t)}</span>
          </div>
        );
      })}
    </div>
    </>
  );
}
