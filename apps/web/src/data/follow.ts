// Ax92 (#435): what the followed ★ player did, for "his match" on the overview and the
// "involved" tags on the turning points. Pure functions over the match events.
import type { MatchEvent, Pivot1 as Pivot } from "@pivot/contracts";
import { involves } from "./view";

/** A turning point's window either side of its minute, in minutes, for the "involved" tag. */
export const INVOLVED_WINDOW_MIN = 5;

/**
 * The player was involved in a turning point when he made, received, or came on or went off in
 * one of its trigger or evidence events, or in any event from 5 minutes before its minute to 5 after.
 */
export function involvedIn(pivot: Pivot, player: string, events: readonly MatchEvent[], eventById: (id: string) => MatchEvent | undefined): boolean {
  const ids = [...pivot.trigger_event_ids, ...(pivot.narrative?.sentences ?? []).flatMap((s) => s.evidence_ids)];
  if (ids.some((id) => { const e = eventById(id); return !!e && involves(e, player); })) return true;
  const from = (pivot.minute - INVOLVED_WINDOW_MIN) * 60;
  const to = (pivot.minute + INVOLVED_WINDOW_MIN) * 60;
  return events.some((e) => e.t >= from && e.t <= to && involves(e, player));
}

export type MomentKind = "goal" | "shotOn" | "shotOff" | "assist" | "keyPass" | "yellow" | "red" | "subOn" | "subOff";
export type PlayerMoment = { kind: MomentKind; event: MatchEvent; /** The other player: the shooter of his key pass. */ other?: string | null };

const ON_TARGET = new Set(["goal", "saved", "disallowed"]);
const cardOf = (e: MatchEvent) => String(e.foul?.card ?? e.meta?.card ?? e.meta?.colour ?? e.meta?.color ?? "");

/**
 * His goals, shots, key passes and assists, cards and substitutions, in match order. A key pass is his
 * completed pass to a team-mate who then shot in the same possession; an assist when that shot was a goal.
 */
export function playerMoments(events: readonly MatchEvent[], player: string): PlayerMoment[] {
  const asc = [...events].sort((a, b) => a.t - b.t || a.seq - b.seq);
  const out: PlayerMoment[] = [];
  for (let i = 0; i < asc.length; i++) {
    const e = asc[i];
    if (e.type === "shot") {
      if (e.player_id === player) out.push({ kind: e.shot_outcome === "goal" ? "goal" : ON_TARGET.has(e.shot_outcome ?? "") ? "shotOn" : "shotOff", event: e });
      // The pass that set it up: the last completed pass to the shooter in the same possession.
      for (let j = i - 1; j >= 0; j--) {
        const p = asc[j];
        if (p.possession_id !== e.possession_id || p.team !== e.team) break;
        if (p.type !== "pass") continue;
        if (p.receiver_id === e.player_id && p.player_id === player && p.player_id !== e.player_id) {
          out.push({ kind: e.shot_outcome === "goal" ? "assist" : "keyPass", event: p, other: e.player_id });
        }
        break;
      }
    } else if (e.type === "card" && e.player_id === player) {
      out.push({ kind: ["red", "second_yellow"].includes(cardOf(e)) ? "red" : "yellow", event: e });
    } else if (e.substitution) {
      if (e.substitution.player_on_id === player) out.push({ kind: "subOn", event: e });
      if (e.substitution.player_off_id === player) out.push({ kind: "subOff", event: e });
    }
  }
  return out.sort((a, b) => a.event.t - b.event.t);
}
