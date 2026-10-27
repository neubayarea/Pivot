// "How do you want to watch?" (C13 #316): asked once, on a first visit, as a strip under the site
// bar that blocks nothing. Fan or analyst is ours alone, no other match site has it, so it is
// offered up front instead of waiting to be found in the bar. Choosing, closing it, or switching
// in the bar retires it for good. A link that already says `?mode=` (a recording) is never asked.
import { useEffect, useRef, useState } from "react";
import type { ViewerPrefs } from "@pivot/contracts";
import { usePrefs } from "../i18n";

const ASKED = "pivot.asked";

/** Ask only when nothing chose a mode yet: no `?mode=`, no saved mode, not asked before. */
export function shouldAsk(search: string, storage: Pick<Storage, "getItem"> | null): boolean {
  if (new URLSearchParams(search).has("mode")) return false;
  try {
    return !!storage && !storage.getItem("pivot.mode") && !storage.getItem(ASKED);
  } catch {
    return false;
  }
}

const remember = () => {
  try {
    window.localStorage.setItem(ASKED, "1");
  } catch {
    // Blocked storage: it asks again next visit, which is harmless.
  }
};

export default function WatchPrompt() {
  const { prefs, setPrefs, t } = usePrefs();
  const [open, setOpen] = useState(() =>
    typeof window !== "undefined" && shouldAsk(window.location.search, (() => { try { return window.localStorage; } catch { return null; } })()));
  const first = useRef(prefs.audience);
  // Switched in the bar meanwhile: that was the answer.
  useEffect(() => {
    if (open && prefs.audience !== first.current) {
      remember();
      setOpen(false);
    }
  }, [prefs.audience, open]);
  if (!open) return null;
  const pick = (audience: ViewerPrefs["audience"]) => {
    remember();
    setOpen(false);
    setPrefs({ ...prefs, audience });
  };
  const close = () => {
    remember();
    setOpen(false);
  };
  return (
    <section className="ask" aria-labelledby="ask-q">
      <div className="ask-in">
        <h2 id="ask-q">{t("ask.q")}</h2>
        <button type="button" className="ask-opt" onClick={() => pick("fan")}>
          <b>{t("ask.fan")}</b>
          <span>{t("ask.fanNote")}</span>
        </button>
        <button type="button" className="ask-opt" onClick={() => pick("analyst")}>
          <b>{t("ask.analyst")}</b>
          <span>{t("ask.analystNote")}</span>
        </button>
        <p className="ask-where">{t("ask.where")}</p>
        <button type="button" className="btn ghost ask-later" onClick={close}>{t("ask.later")}</button>
      </div>
    </section>
  );
}
