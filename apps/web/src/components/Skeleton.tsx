import { useT } from "../i18n";

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
export function Placeholder({ label, lines = 2, block, chips, className }: {
  label: string;
  /** Text-line bars under the block. */
  lines?: number;
  /** Height in px of one tall block (a chart, a pitch, a card). */
  block?: number;
  /** A row of short pills, the shape of a set of choices. */
  chips?: number;
  className?: string;
}) {
  return (
    <div className={className ? `ph ${className}` : "ph"} aria-busy="true">
      <span className="sr-only" role="status">{label}</span>
      <div className="ph-body" aria-hidden="true">
        {block !== undefined && <span className="sk sk-shim ph-block" style={{ height: block }} />}
        {chips !== undefined && (
          <span className="ph-chips">{Array.from({ length: chips }, (_, i) => <span key={i} className="sk sk-shim ph-chip" />)}</span>
        )}
        {Array.from({ length: lines }, (_, i) => <span key={i} className="sk sk-shim sk-line" />)}
      </div>
    </div>
  );
}
