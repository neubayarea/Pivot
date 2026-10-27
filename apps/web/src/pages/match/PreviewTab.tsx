// 赛前 · Preview (C13 #316): the build-up without the line-ups, which have their own tab now:
// form, table and head-to-head first, then the news, ties and context effects (Carry3's pieces).
// #315: the form in detail (home and away, the last five with half-time scores, the next match and
// who rests) follows the build-up, from its own endpoint; it is left out until that answers.
// #311: the blocks follow `ORDER[audience].pre`: fans read the storylines first, analysts the
// numbers first. The ids this tab has no block for (your team, spotlight, and the plan and
// line-ups, which live on the line-ups tab) are skipped.
import { Fragment, useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { PreMatchStories, PreMatchTop } from "../../components/PreMatch";
import PreMatchDeep from "../../components/PreMatchDeep";
import StartDemoButton from "../../components/StartDemoButton";
import { useHeightVar } from "../../data/headerFold";
import { useMatch } from "../../data/match";
import { usePersona } from "../../data/persona";
import { useT } from "../../i18n";

type Stop = { id: string; label: string };

/** A heading's own words, without the note in its <small>. */
function headingLabel(h: Element): string {
  const copy = h.cloneNode(true) as Element;
  copy.querySelectorAll("small").forEach((s) => s.remove());
  return copy.textContent?.trim() ?? "";
}

/** Ax78 (#374): "on this page" under the tabs, one stop per section heading of the tab, in page order.
 * The stops are read off the page, so they follow the audience order, the language and the parts
 * that load later (the form in detail); the row sticks under the tabs like the What-if chips. */
function PreviewNav({ root }: { root: RefObject<HTMLDivElement | null> }) {
  const t = useT();
  const row = useHeightVar("--pv-sub-h");
  const [stops, setStops] = useState<Stop[]>([]);
  const [here, setHere] = useState<string | null>(null);
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const read = () => {
      const next = [...el.querySelectorAll("h2[id], h3[id]")]
        .map((h) => ({ id: h.id, label: headingLabel(h) }))
        .filter((s) => s.label);
      setStops((old) => (old.length === next.length && old.every((o, i) => o.id === next[i].id && o.label === next[i].label) ? old : next));
    };
    read();
    const mo = new MutationObserver(read);
    mo.observe(el, { childList: true, subtree: true, characterData: true });
    return () => mo.disconnect();
  }, [root]);
  useEffect(() => {
    if (!stops.length) return;
    // The section under the sticky stack is the one being read.
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

export function PreviewTab() {
  const root = useRef<HTMLDivElement>(null);
  const t = useT();
  const { preMatch, match } = useMatch();
  const { order } = usePersona();
  // Before kick-off this is the tab the match opens on, so it is where the match is started.
  const start = match.status === "scheduled" && (
    <div className="live-start">
      <p className="muted">{t("board.kickoffPending")}</p>
      <StartDemoButton matchId={match.match_id}>{t("demo.startMatch")}</StartDemoButton>
    </div>
  );
  if (!preMatch) return <>{start}<p className="muted">{t("tabs.previewNone")}</p><PreMatchDeep /></>;
  // Form and head-to-head are one build-up section, so "form" places it whole, the detail after it.
  const blocks: Partial<Record<(typeof order.pre)[number], ReactNode>> = {
    form: (
      <>
        <section className="post-sec pre-slot" data-slot="prematch" aria-labelledby="pre-buildup-hd">
          <header className="sec-hd">
            <h2 id="pre-buildup-hd">{t("pre.buildUp")}</h2>
            <p className="muted">{t("pre.buildUpNote")}</p>
          </header>
          <PreMatchTop />
        </section>
        <PreMatchDeep />
      </>
    ),
    stories: <PreMatchStories />,
  };
  return (
    <>
      <PreviewNav root={root} />
      {start}
      <div ref={root} className="pv-body">
        {order.pre.map((id) => blocks[id] && <Fragment key={id}>{blocks[id]}</Fragment>)}
      </div>
    </>
  );
}
