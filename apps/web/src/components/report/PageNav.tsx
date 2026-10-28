// "On this page" for the Stats tab (C20, #391), the same row as the Preview tab's (#375): one stop per
// section heading (h2 with an id) in page order, read off the page so it follows the audience, the
// language and the parts that load later; it sticks under the tabs and marks the section being read.
import { useEffect, useState, type RefObject } from "react";
import { useHeightVar } from "../../data/headerFold";
import { useT } from "../../i18n";

type Stop = { id: string; label: string };

const labelOf = (h: Element) => {
  const copy = h.cloneNode(true) as Element;
  copy.querySelectorAll("small, .rp-live").forEach((s) => s.remove());
  return copy.textContent?.trim() ?? "";
};

export default function PageNav({ root }: { root: RefObject<HTMLElement | null> }) {
  const t = useT();
  const row = useHeightVar("--pv-sub-h");
  const [stops, setStops] = useState<Stop[]>([]);
  const [here, setHere] = useState<string | null>(null);
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const read = () => {
      const next = [...el.querySelectorAll("h2[id]")].map((h) => ({ id: h.id, label: labelOf(h) })).filter((s) => s.label);
      setStops((old) => (old.length === next.length && old.every((o, i) => o.id === next[i].id && o.label === next[i].label) ? old : next));
    };
    read();
    const mo = new MutationObserver(read);
    mo.observe(el, { childList: true, subtree: true, characterData: true });
    return () => mo.disconnect();
  }, [root]);
  useEffect(() => {
    if (!stops.length) return;
    const onScroll = () => {
      const top = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0;
      let current: string | null = stops[0].id;
      for (const s of stops) {
        const h = document.getElementById(s.id);
        if (h && h.getBoundingClientRect().top <= top + 8) current = s.id;
      }
      setHere(current);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [stops]);
  if (stops.length < 2) return null;
  return (
    <nav ref={row} className="chips wi-pivots pv-nav" aria-label={t("pre.navLabel")}>
      {stops.map((s) => (
        <button key={s.id} type="button" className="chip" aria-current={here === s.id ? "location" : undefined}
          onClick={() => document.getElementById(s.id)?.scrollIntoView({ behavior: "smooth", block: "start" })}>
          {s.label}
        </button>
      ))}
    </nav>
  );
}
