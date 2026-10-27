// What each player did, for the line-ups once the match is under way (Ax69), the way FotMob and the
// Premier League site show it: goals, cards, the minute they came on or went off, and their rating.
// Goals, cards and changes come from the visible events; the rating from the player stats (#226).
import type { MatchEvent, PlayerReport } from "@pivot/contracts";
import { goalFor } from "./keyMoments";
import { isRedCard } from "./view";

export type Facts = { goals: number; yellow: boolean; red: boolean; on?: number; off?: number; rating?: number };

/** Per player id; `t` of a change is the elapsed second, for the page's minute labels. An own goal is not the scorer's. */
export function lineupFacts(events: readonly MatchEvent[], players: readonly PlayerReport[] = []): Map<string, Facts> {
  const out = new Map<string, Facts>();
  const of = (id: string) => {
    let f = out.get(id);
    if (!f) out.set(id, (f = { goals: 0, yellow: false, red: false }));
    return f;
  };
  // Oldest first, so a second yellow turns the yellow into a red.
  for (const e of [...events].sort((a, b) => a.t - b.t)) {
    if (e.type === "shot" && goalFor(e) === e.team && e.player_id) of(e.player_id).goals++;
    if (e.type === "card" && e.player_id) {
      if (isRedCard(e)) of(e.player_id).red = true;
      else of(e.player_id).yellow = true;
    }
    if (e.substitution) {
      of(e.substitution.player_on_id).on = e.t;
      of(e.substitution.player_off_id).off = e.t;
    }
  }
  for (const p of players) if (p.stats && p.stats.minutes_played > 0) of(p.player_id).rating = p.stats.rating;
  return out;
}

/** Pitch labels: a long surname is cut to its first seven letters and a full stop, so neighbours do not run into each other. */
export const shortName = (surname: string, max = 9) => (surname.length > max ? `${surname.slice(0, 7)}.` : surname);
