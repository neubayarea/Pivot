// The viewer's ♥ team follows the club, not the side (QA round 4, #354). `focus_team` stays a side,
// as the API reads it, but which club it means is saved too (`pivot.club`, its short name): when a
// match opens where that club plays away, the ♥ moves to the away side. A choice saved before this
// (a side only) meant Harbour City v Northgate Rovers, the only fixture there was.
import { useEffect, useRef } from "react";
import { usePrefs } from "../i18n";
import { useHub } from "./hub";
import { useMatch, type Side } from "./match";

const CLUB_KEY = "pivot.club";
const LEGACY: Record<Side, string> = { home: "HBC", away: "ROV" };

type Teams = Record<Side, { short_name: string }>;

function readClub(): string | null {
  try {
    return window.localStorage.getItem(CLUB_KEY);
  } catch {
    return null;
  }
}

function saveClub(club: string | null): void {
  try {
    if (club) window.localStorage.setItem(CLUB_KEY, club);
    else window.localStorage.removeItem(CLUB_KEY);
  } catch {
    // The ♥ still works on this page; it just goes back to a side on reload.
  }
}

/** The side `club` plays on in this match, or null when it does not play. */
export function sideOfClub(teams: Teams, club: string | null): Side | null {
  return club === teams.home.short_name ? "home" : club === teams.away.short_name ? "away" : null;
}

/**
 * The club a saved choice means when this match opens: the saved club, else (a choice from before
 * clubs were saved) the club on that side of Harbour City v Northgate Rovers.
 */
export function savedClub(club: string | null, side: Side | null): string | null {
  return club ?? (side ? LEGACY[side] : null);
}

/** Keeps `focus_team` on the viewer's club in `teams`, and remembers the club they pick. */
export function useFollowClub(teams: Teams | null) {
  const { prefs, setPrefs } = usePrefs();
  const seen = useRef<string | null>(null);
  const moved = useRef(false);
  const key = teams ? `${teams.home.short_name}|${teams.away.short_name}` : null;
  useEffect(() => {
    if (!teams || !key) return;
    if (key !== seen.current) {
      // Another match: the saved club decides the side.
      seen.current = key;
      const club = savedClub(readClub(), prefs.focus_team);
      const side = sideOfClub(teams, club);
      if (club && side !== prefs.focus_team) {
        // Moved to the club's side, or off both sides in a match it does not play; the club stays saved.
        moved.current = true;
        saveClub(club);
        setPrefs({ ...prefs, focus_team: side });
        return;
      }
    } else if (moved.current) {
      moved.current = false;
      return;
    }
    // The viewer's own pick (or the one just resolved): remember its club.
    saveClub(prefs.focus_team ? teams[prefs.focus_team].short_name : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, prefs.focus_team]);
}

/** On a match page. */
export function FollowClub() {
  useFollowClub(useMatch().teams);
  return null;
}

/** On the match centre: its teams are the live match's, or the first listed. */
export function FollowClubOnHub() {
  const { data } = useHub();
  const first = data?.matches.find((m) => m.live) ?? data?.matches[0] ?? null;
  useFollowClub(first && { home: first.home, away: first.away });
  return null;
}
