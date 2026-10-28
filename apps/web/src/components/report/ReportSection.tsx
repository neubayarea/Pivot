// One section of the analyst's post-match report (C19, #385): a heading, the one-sentence takeaway
// the data gives, the chart, and where its numbers come from.
import type { ReactNode } from "react";
import { useT } from "../../i18n";

type Props = {
  id: string; title: string; takeaway?: string | null; source: string; className?: string; children: ReactNode;
  /** A line under the heading, e.g. that a live match's numbers still move. */
  note?: string | null;
  /** h2 when the section is a stop on the page's "on this page" row (the Stats tab), h3 inside a section. */
  level?: 2 | 3;
  /** The match is still on (or replayed short of full time): marks the section as "so far". */
  live?: boolean;
};

export default function ReportSection({ id, title, takeaway, source, className = "", children, note, level = 3, live = false }: Props) {
  const H = level === 2 ? "h2" : "h3";
  const t = useT();
  return (
    <section className={`rp-sec${live ? " live" : ""} ${className}`.trim()} aria-labelledby={`${id}-hd`} id={id}>
      <header className="rp-hd">
        <H id={`${id}-hd`}>{title}</H>
        {live && <span className="rp-live">{t("rp.soFar")}</span>}
      </header>
      {note && <p className="rp-note muted">{note}</p>}
      {takeaway && <p className="rp-take">{takeaway}</p>}
      {children}
      <p className="rp-src">{t("rp.source", { what: source })}</p>
    </section>
  );
}
