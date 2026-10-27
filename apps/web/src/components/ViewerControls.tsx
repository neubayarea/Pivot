// The viewer's own controls, fan / analyst, ♥ team and ★ player, in the site bar next to the
// language (Ax68), so they are there on every tab whether the score header is open or slim.
// On phones they would not fit in the bar: one "View" button opens them in a small panel.
import { useEffect, useId, useRef, useState } from "react";
import type { ViewerPrefs } from "@pivot/contracts";
import { useMatch } from "../data/match";
import { useT, type T } from "../i18n";
import { PlayerPicker, TeamPicker } from "./FocusPickers";
import Segmented from "./Segmented";

const audiences = (t: T) => [
  { value: "fan", label: t("top.audience.fan") },
  { value: "analyst", label: t("top.audience.analyst") },
] as const;

type Props = {
  prefs: ViewerPrefs;
  onPrefsChange: (prefs: ViewerPrefs) => void;
};

export default function ViewerControls({ prefs, onPrefsChange }: Props) {
  const { squads } = useMatch();
  const t = useT();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const id = useId();

  // A player saved while watching another match is not in this one; the API would refuse him.
  const player = prefs.focus_player_id;
  const known = !player || squads.home.length + squads.away.length === 0
    || [...squads.home, ...squads.away].some((p) => p.player_id === player);
  useEffect(() => {
    if (!known) onPrefsChange({ ...prefs, focus_player_id: null });
  }, [known]);

  // The phone panel closes on Escape (focus back to its button) or a press outside it. While the
  // player list is open inside it, Escape is that list's to close first.
  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent) {
        if (e.key !== "Escape" || root.current?.querySelector(".pick-pop")) return;
        setOpen(false);
        button.current?.focus();
      } else if (!root.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  return (
    <div className={`top-view${open ? " open" : ""}`} ref={root}>
      <button ref={button} type="button" className="btn top-view-btn" aria-expanded={open} aria-controls={id}
        onClick={() => setOpen(!open)}>
        {t("top.view")} <span aria-hidden="true">▾</span>
      </button>
      <div id={id} className="top-view-panel" role="group" aria-label={t("header.controls")}>
        <Segmented
          label={t("top.audience")}
          options={audiences(t)}
          value={prefs.audience}
          onChange={(audience) => onPrefsChange({ ...prefs, audience })}
        />
        <TeamPicker prefs={prefs} onPrefsChange={onPrefsChange} />
        <PlayerPicker prefs={prefs} onPrefsChange={onPrefsChange} />
      </div>
    </div>
  );
}
