// ☆ Follow / ★ Following (C13 #316): one button to follow a player from wherever they appear,
// the player card, the pitch, the line-ups, instead of only from the picker in the bar. Pressing
// it again stops following. It writes the same viewer setting the picker does (`focus_player_id`).
import { usePrefs } from "../i18n";

export default function FollowButton({ playerId, name }: { playerId: string; name: string }) {
  const { prefs, setPrefs, t } = usePrefs();
  const on = prefs.focus_player_id === playerId;
  return (
    <button type="button" className={`follow${on ? " on" : ""}`} aria-pressed={on}
      aria-label={t(on ? "follow.stopLabel" : "follow.label", { name })}
      onClick={() => setPrefs({ ...prefs, focus_player_id: on ? null : playerId })}>
      <span aria-hidden="true">{on ? "★" : "☆"}</span> {t(on ? "follow.following" : "follow.follow")}
    </button>
  );
}
