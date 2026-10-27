// The ♥ beside a team's name (Ax69, #322): in the score header, slim or open, and on the line-ups
// tab before a team is picked. It picks that team as the viewer's, and pressed again lets it go.
// The same setting as the ♥ picker in the site bar (ViewerControls); the heart is in the kit colour.
import type { CSSProperties } from "react";
import { useMatch, type Side } from "../data/match";
import { toggled } from "../data/matchup";
import { usePrefs } from "../i18n";

export default function FollowTeam({ side, withName = false }: { side: Side; withName?: boolean }) {
  const { teams } = useMatch();
  const { prefs, setPrefs, t } = usePrefs();
  const on = prefs.focus_team === side;
  const label = t(on ? "follow.teamOff" : "follow.team", { team: teams[side].name });
  return (
    <button type="button" className={`fav-btn ${side}${on ? " on" : ""}${withName ? " named" : ""}`} aria-pressed={on}
      aria-label={withName ? undefined : label} title={label} style={{ "--tc": `var(--pv-${side})` } as CSSProperties}
      onClick={() => setPrefs({ ...prefs, focus_team: toggled(prefs.focus_team, side) })}>
      <span aria-hidden="true">{on ? "♥" : "♡"}</span>
      {withName && <span>{teams[side].name}</span>}
    </button>
  );
}

/** "Following: Moreau ✕" under the score header while a ★ player is followed; ✕ stops following. */
export function FollowingChip() {
  const { playerName } = useMatch();
  const { prefs, setPrefs, t } = usePrefs();
  const id = prefs.focus_player_id;
  if (!id) return null;
  const name = playerName(id);
  return (
    <p className="follow-chip" role="status">
      <span>★ {t("follow.chip", { player: name })}</span>
      <button type="button" className="follow-x" aria-label={t("follow.stop", { player: name })} title={t("follow.stop", { player: name })}
        onClick={() => setPrefs({ ...prefs, focus_player_id: null })}>
        <span aria-hidden="true">✕</span>
      </button>
    </p>
  );
}
