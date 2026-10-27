// Which match S1, S2 and the overlay show (Ax6). `?match=` wins, then the viewer's last pick
// (localStorage), else the default: the first match the API lists, i.e. the first seed (Ax55).
// A linked match that is gone (an old link) falls back to the default, with a line saying so.
// The picker in the top bar lists the API's matches and polls while the server is still generating
// its simulated ones.
import { createContext, useContext, useEffect, useState } from "react";
import type { Match } from "@pivot/contracts";
import type { T } from "../i18n";
import { api, type SimsStatus } from "./live/api";

const STORAGE_KEY = "pivot.match";
/** The hand-made sample match the API seeds for frontend work (apps/api demo.py). */
export const DEMO_MATCH_ID = "M-api-demo";
/** The recorded demo (B02): test data, only on a server started with PIVOT_DEMO_FIXTURE (Ax55). */
export const DEMO_PRESET = "demo-1021";

export const isRecordedDemo = (m: Match) => m.preset === DEMO_PRESET;
const POLL_MS = 2000;

/** `fromUrl`: a match named in the link that is missing is reported (`missing`); a saved one is just dropped. */
export type MatchChoice = { id: string | null; fromUrl: boolean };

export function readSavedMatch(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY) || null;
  } catch {
    return null;
  }
}

export function saveMatch(id: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // Not remembered across reloads, but the page still switches.
  }
}

export function initialMatch(search: string, saved: string | null): MatchChoice {
  const asked = new URLSearchParams(search).get("match");
  return asked ? { id: asked, fromUrl: true } : { id: saved, fromUrl: false };
}

/** The matchday of a season fixture, from its id ("S2026-31-LUN-HBC" is matchday 31); null for any other match. */
export const matchdayOf = (id: string): number | null => {
  const m = /^S\d{4}-(\d+)-/.exec(id);
  return m ? Number(m[1]) : null;
};

/** "HBC 4–5 ROV (game 101)"; the recorded demo and the hand-made sample say so instead of a seed. */
export function matchLabel(m: Match, t: T): string {
  // C14: a fixture of the next round has no score and no seed worth showing yet:
  // "Lunsford Sporting v Harbour City · MD31" (#354), never its id.
  if (m.status === "scheduled") {
    const md = matchdayOf(m.match_id);
    return `${m.home.name} v ${m.away.name} · ${md === null ? t("picker.next") : t("picker.matchday", { n: md })}`;
  }
  const tag = isRecordedDemo(m)
    ? t("picker.demo")
    : m.match_id === DEMO_MATCH_ID
      ? t("picker.sample")
      : t("picker.seed", { seed: m.seed });
  const status = m.status === "finished" ? "" : `, ${t(`status.${m.status}`)}`;
  return `${m.home.short_name} ${m.score.home}–${m.score.away} ${m.away.short_name} (${tag}${status})`;
}

/** `missing`: the match the link asked for, when it was gone and the default is shown instead. */
type ChoiceValue = { choice: MatchChoice; choose: (id: string) => void; missing: string | null; dismiss: () => void };

/** Only set while following the API; the fixture replay has one match and no picker. */
export const MatchChoiceContext = createContext<ChoiceValue | null>(null);

export const useMatchChoice = () => useContext(MatchChoiceContext);

export type MatchList = { matches: Match[]; sims: SimsStatus | null };

/** The API's matches, refetched every couple of seconds until the simulated ones are all stored. */
export function useMatchList(enabled: boolean): MatchList {
  const [list, setList] = useState<MatchList>({ matches: [], sims: null });
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      const [matches, sims] = await Promise.all([
        api.listMatches().catch(() => null),
        api.sims().catch(() => null),
      ]);
      if (!alive) return;
      setList((prev) => ({ matches: matches ?? prev.matches, sims }));
      if (sims?.generating || matches === null) timer = setTimeout(load, POLL_MS);
    };
    load();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [enabled]);
  return list;
}
