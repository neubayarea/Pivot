// Interface language and viewing mode. One small table per language (messages/*.ts), looked up by
// key; a key a language lacks falls back to English (with a dev-mode warning), never to blank.
// The language is chosen by `?lang=` (for recordings), then the saved choice, then the browser.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { ViewerPrefs } from "@pivot/contracts";
import { en } from "./messages/en";
import { es } from "./messages/es";
import { zh } from "./messages/zh";

export type Lang = ViewerPrefs["language"];
export type MessageKey = keyof typeof en;
export type Messages = Partial<Record<MessageKey, string>>;
export type Vars = Record<string, string | number>;
export type T = (key: MessageKey, vars?: Vars) => string;

export const LANGS: readonly Lang[] = ["en", "zh", "es"];
const TABLES: Record<Lang, Messages> = { en, zh, es };
const STORAGE_KEY = "pivot.lang";
/** What `<html lang>` gets, so the browser picks Simplified Chinese glyphs and the CSS can switch fonts. */
const HTML_LANG: Record<Lang, string> = { en: "en", zh: "zh-Hans", es: "es" };

export const DEFAULT_PREFS: ViewerPrefs = { audience: "analyst", language: "en", focus_team: null, focus_player_id: null };

/** For keys built from data (`metric.${name}`): true when the English table has it. */
export const isMessageKey = (key: string): key is MessageKey => key in en;

const isLang = (v: unknown): v is Lang => typeof v === "string" && (LANGS as readonly string[]).includes(v);

const warned = new Set<string>();

/** A t() for one language. `tables` is only swapped in tests. */
export function translator(lang: Lang, tables: Record<Lang, Messages> = TABLES): T {
  return (key, vars) => {
    let text = tables[lang][key];
    if (text === undefined) {
      if (import.meta.env.DEV && lang !== "en" && !warned.has(`${lang}:${key}`)) {
        warned.add(`${lang}:${key}`);
        console.warn(`[i18n] "${key}" has no ${lang} translation; using English.`);
      }
      text = tables.en[key] ?? key;
    }
    return vars ? text.replace(/\{(\w+)\}/g, (m, name: string) => (name in vars ? String(vars[name]) : m)) : text;
  };
}

/** The saved choice; null when there is none or storage is blocked (private mode, sandboxed frame). */
export function readSavedLang(): Lang | null {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return isLang(v) ? v : null;
  } catch {
    return null;
  }
}

export function saveLang(lang: Lang): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // Not remembered across reloads, but the page still switches.
  }
}

/** `?lang=` beats the saved choice, which beats the browser's languages; English otherwise. */
export function initialLang(search: string, saved: Lang | null, browser: readonly string[]): Lang {
  const asked = new URLSearchParams(search).get("lang");
  if (isLang(asked)) return asked;
  if (saved) return saved;
  for (const tag of browser) {
    const base = tag.toLowerCase().split("-")[0];
    if (isLang(base)) return base;
  }
  return "en";
}

function startLang(): Lang {
  if (typeof window === "undefined") return "en";
  const browser = typeof navigator === "undefined" ? [] : (navigator.languages ?? [navigator.language]);
  return initialLang(window.location.search, readSavedLang(), browser.filter(Boolean));
}

type PrefsValue = { prefs: ViewerPrefs; setPrefs: (prefs: ViewerPrefs) => void; t: T };

// Without a provider (tests, a crash above it) the page reads English with the default viewing mode.
const PrefsContext = createContext<PrefsValue>({ prefs: DEFAULT_PREFS, setPrefs: () => {}, t: translator("en") });

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefsState] = useState<ViewerPrefs>(() => ({ ...DEFAULT_PREFS, language: startLang() }));

  useEffect(() => {
    document.documentElement.lang = HTML_LANG[prefs.language];
  }, [prefs.language]);

  const value = useMemo<PrefsValue>(() => ({
    prefs,
    setPrefs: (next) => {
      if (next.language !== prefs.language) saveLang(next.language);
      setPrefsState(next);
    },
    t: translator(prefs.language),
  }), [prefs]);

  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export const usePrefs = () => useContext(PrefsContext);
export const useT = () => useContext(PrefsContext).t;
export const useLang = () => useContext(PrefsContext).prefs.language;

/** The language a narrative was actually written in; the API falls back to English when it cannot write the asked one. */
export const narrativeLang = (n: { prefs: ViewerPrefs } | null | undefined): Lang | null => n?.prefs.language ?? null;

/** True when pivots fetched for these prefs differ from what the WebSocket pushes (English, analyst). */
export const needsLocalised = (p: ViewerPrefs) =>
  p.language !== "en" || p.audience !== "analyst" || p.focus_team !== null || p.focus_player_id !== null;
