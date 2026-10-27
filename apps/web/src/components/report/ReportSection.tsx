// One section of the analyst's post-match report (C19, #385): a heading, the one-sentence takeaway
// the data gives, the chart, and where its numbers come from.
import type { ReactNode } from "react";
import { useT } from "../../i18n";

type Props = { id: string; title: string; takeaway?: string | null; source: string; className?: string; children: ReactNode };

export default function ReportSection({ id, title, takeaway, source, className = "", children }: Props) {
  const t = useT();
  return (
    <section className={`rp-sec ${className}`.trim()} aria-labelledby={`${id}-hd`} id={id}>
      <header className="rp-hd">
        <h3 id={`${id}-hd`}>{title}</h3>
      </header>
      {takeaway && <p className="rp-take">{takeaway}</p>}
      {children}
      <p className="rp-src">{t("rp.source", { what: source })}</p>
    </section>
  );
}
