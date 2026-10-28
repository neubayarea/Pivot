import { useT, type T } from "../i18n";
import type { LoadFault } from "../data/live/api";

export { faultOf, type LoadFault } from "../data/live/api";

/** Card outlines in the shape of S1, shown until the first load. No spinner: the layout is the progress. */
export default function Skeleton() {
  const t = useT();
  const card = (lines: number, tall = false) => (
    <section className="card sk-card" aria-hidden="true">
      <h3><span className="sk sk-title" /></h3>
      {tall && <span className="sk sk-block" />}
      {Array.from({ length: lines }, (_, i) => <span key={i} className="sk sk-line" />)}
    </section>
  );
  return (
    <div aria-busy="true">
      <p className="sr-only" role="status">{t("startup.loading")}</p>
      <div className="headline" aria-hidden="true">
        <span className="sk sk-head" />
      </div>
      <div className="grid1">
        <div className="stack">
          {card(0, true)}
          <div className="lower">
            {card(4)}
            {card(6)}
          </div>
        </div>
        <div className="stack">
          {card(5)}
          {card(4)}
        </div>
      </div>
    </div>
  );
}

/**
 * Ax79: neutral grey blocks in the shape of the content that is on its way, so the page does not jump
 * when it lands. The loading words stay in the page for screen readers (and for tests), hidden from sight.
 */
export function Placeholder({ label, lines = 2, block, ratio, chips, className }: {
  label: string;
  /** Text-line bars under the block. */
  lines?: number;
  /** Height in px of one tall block (a chart, a pitch, a card). */
  block?: number;
  /** Width over height of one full-width block instead, so it holds the final shape at any width (a pitch: 105 / 68). */
  ratio?: number;
  /** A row of short pills, the shape of a set of choices. */
  chips?: number;
  className?: string;
}) {
  return (
    <div className={className ? `ph ${className}` : "ph"} aria-busy="true">
      <span className="sr-only" role="status">{label}</span>
      <div className="ph-body" aria-hidden="true">
        {block !== undefined && <span className="sk sk-shim ph-block" style={{ height: block }} />}
        {ratio !== undefined && <span className="sk sk-shim ph-block" style={{ aspectRatio: String(ratio) }} />}
        {chips !== undefined && (
          <span className="ph-chips">{Array.from({ length: chips }, (_, i) => <span key={i} className="sk sk-shim ph-chip" />)}</span>
        )}
        {Array.from({ length: lines }, (_, i) => <span key={i} className="sk sk-shim sk-line" />)}
      </div>
    </div>
  );
}

/** The fault in the viewer's words. */
export function faultText(fault: LoadFault, t: T): string {
  if (fault === "offline") return t("load.reason.offline");
  if (fault === "data") return t("load.reason.data");
  return t(fault >= 400 && fault < 500 ? "load.reason.refused" : "load.reason.server", { status: fault });
}

/**
 * Ax79: what failed, why, and a Retry that asks again, in place of a placeholder that would
 * otherwise stay up for ever. `tall` keeps the height of the block it replaces (a pitch, a chart).
 */
export function LoadFailed({ message, fault, onRetry, ratio, className }: {
  message: string;
  fault?: LoadFault | null;
  onRetry?: () => void;
  ratio?: number;
  className?: string;
}) {
  const t = useT();
  return (
    <div className={`load-failed${ratio ? " tall" : ""}${className ? ` ${className}` : ""}`} role="alert"
      style={ratio ? { aspectRatio: String(ratio) } : undefined}>
      <p>
        <b>{message}</b>
        {fault != null && <> <span className="muted">{faultText(fault, t)}</span></>}
      </p>
      {onRetry && <button type="button" className="btn" onClick={onRetry}>{t("load.retry")}</button>}
    </div>
  );
}

const reducedMotion = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Fades in an element that has just replaced a placeholder (~180 ms of opacity, nothing moves); off under reduced motion. */
export function fadeIn(el: Element | null | undefined) {
  if (!el || reducedMotion() || typeof (el as HTMLElement).animate !== "function") return;
  (el as HTMLElement).animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180, easing: "ease-out" });
}

// One function for every marker, so React calls it once on mount and not on each render.
const fadeNext = (el: HTMLSpanElement | null) => fadeIn(el?.nextElementSibling);

/** An empty marker that fades in the element right after it, for content that is not ours to give a class. */
export function FadeNext() {
  return <span hidden ref={fadeNext} />;
}

/** Three dots that breathe in turn, beside words that say what is being worked on (never on their own). */
export function WorkingDots() {
  return <span className="wr-dots" aria-hidden="true"><i /><i /><i /></span>;
}
