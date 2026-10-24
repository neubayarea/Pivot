// The ♥ team and ★ player pickers in the top bar (C08). The team is a plain select; the player
// picker opens a searchable list of both squads, since 22+ names are too many to scroll through.
import { useEffect, useId, useRef, useState } from "react";
import type { ViewerPrefs } from "@pivot/contracts";
import { useMatch, type Side } from "../data/match";
import { useT } from "../i18n";

type Props = { prefs: ViewerPrefs; onPrefsChange: (prefs: ViewerPrefs) => void };

export function TeamPicker({ prefs, onPrefsChange }: Props) {
  const { teams } = useMatch();
  const t = useT();
  const team = prefs.focus_team;
  const shown = team ? teams[team].short_name : t("top.team.short");
  return (
    <label className={`pick${team ? " set" : ""}`} title={team ? t("top.team", { team: teams[team].name }) : t("top.team.label")}>
      ♥ <em><span className="pick-label">{shown} </span>▾</em>
      <select aria-label={t("top.team.label")} value={team ?? ""}
        onChange={(e) => onPrefsChange({ ...prefs, focus_team: (e.target.value || null) as Side | null })}>
        <option value="">{t("top.team.none")}</option>
        <option value="home">{teams.home.name}</option>
        <option value="away">{teams.away.name}</option>
      </select>
    </label>
  );
}

/** Lower-case, accents stripped, so "rene" finds "René". */
const fold = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

/** "A. Moreau" → "Moreau": what fits in the bar and what the explanations usually say. */
export const surname = (name: string) => name.slice(name.lastIndexOf(" ") + 1);

export function PlayerPicker({ prefs, onPrefsChange }: Props) {
  const { teams, squads, playerName } = useMatch();
  const t = useT();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const root = useRef<HTMLSpanElement>(null);
  const listId = useId();
  const id = prefs.focus_player_id;

  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const pick = (player: string | null) => {
    onPrefsChange({ ...prefs, focus_player_id: player });
    setOpen(false);
    setQuery("");
  };

  const q = fold(query.trim());
  const sides: Side[] = ["home", "away"];
  const groups = sides.map((side) => ({
    side,
    players: squads[side].filter((p) => !q || fold(p.name).includes(q) || String(p.shirt ?? "") === q),
  }));
  const none = groups.every((g) => !g.players.length);

  return (
    <span className="picker" ref={root}>
      <button type="button" className={`pick${id ? " set" : ""}`} aria-haspopup="dialog" aria-expanded={open}
        aria-controls={open ? listId : undefined}
        title={id ? t("top.player", { player: playerName(id) }) : t("top.player.label")}
        onClick={() => setOpen(!open)}>
        ★ <em><span className="pick-label">{id ? surname(playerName(id)) : t("top.player.short")} </span>▾</em>
      </button>
      {open && (
        <div className="pick-pop" role="dialog" aria-label={t("top.player.label")}>
          <input type="search" autoFocus placeholder={t("top.player.search")} aria-label={t("top.player.search")}
            value={query} onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              // Enter takes the first match, so "mor⏎" is enough.
              const first = groups.find((g) => g.players.length)?.players[0];
              if (e.key === "Enter" && first) pick(first.player_id);
            }} />
          {/* Buttons, not a listbox: Tab reaches each one, and the first match is an Enter away. */}
          <div id={listId} className="pick-list">
            {!q && (
              <button type="button" className="none" aria-pressed={id === null} onClick={() => pick(null)}>
                {t("top.player.none")}
              </button>
            )}
            {groups.map((g) => g.players.length > 0 && (
              <div key={g.side} role="group" aria-label={teams[g.side].name}>
                <span className={`grp ${g.side === "home" ? "h" : "a"}`}>{teams[g.side].name}</span>
                {g.players.map((p) => (
                  <button key={p.player_id} type="button" aria-pressed={p.player_id === id} onClick={() => pick(p.player_id)}>
                    <span className="no num">{p.shirt ?? ""}</span> {p.name}
                  </button>
                ))}
              </div>
            ))}
            {none && <p className="muted none">{t("top.player.empty")}</p>}
          </div>
        </div>
      )}
    </span>
  );
}
