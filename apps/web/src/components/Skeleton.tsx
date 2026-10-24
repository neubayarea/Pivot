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
