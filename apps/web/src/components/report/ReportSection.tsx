// One section of the analyst's post-match report (C19, #385): a heading, the one-sentence takeaway
// the data gives, the chart, and where its numbers come from.
import type { ReactNode } from "react";
import { useT } from "../../i18n";

type Props = { id: string; title: string; takeaway?: string | null; source: string; sample?: boolean; className?: string; children: ReactNode };

export default function ReportSection({ id, title, takeaway, source, sample = false, className = "", children }: Props) {
  const t = useT();
  return (
    <section className={`rp-sec ${className}`.trim()} aria-labelledby={`${id}-hd`} id={id}>
      <header className="rp-hd">
        <h3 id={`${id}-hd`}>{title}</h3>
        {sample && <span className="rp-sample" title={t("rp.sampleNote")}>{t("rp.sample")}</span>}
      </header>
      {takeaway && <p className="rp-take">{takeaway}</p>}
      {children}
      <p className="rp-src">{t("rp.source", { what: source })}</p>
    </section>
  );
}
