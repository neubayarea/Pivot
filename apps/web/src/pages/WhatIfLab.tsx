import { Link, useParams } from "react-router-dom";
import Button from "../components/Button";
import Card from "../components/Card";
import Kicker from "../components/Kicker";
import Stamp from "../components/Stamp";
import { useT } from "../i18n";

// S3 · What-if lab. Placeholder layout; scenario form and results come later.
export default function WhatIfLab() {
  const { id = "" } = useParams();
  const t = useT();

  return (
    <>
      <div className="back">
        <Link to={`/pivot/${id}`}>{t("whatif.back", { id })}</Link>
      </div>
      <div className="headline">
        <Kicker>{t("whatif.kicker")}</Kicker>
        <span className="x">{t("whatif.question")}</span>
        <span className="sp" />
        <Stamp tone="warn">{t("whatif.simulated")}</Stamp>
      </div>
      <div className="grid3">
        <Card title={t("whatif.scenario")}>
          <p className="muted">{t("whatif.pick")}</p>
          <div>
            <Button variant="primary">{t("whatif.run")}</Button>
          </div>
        </Card>
        <Card title={t("whatif.outcome")} note={t("whatif.placeholder")}>
          <div className="placeholder">{t("whatif.distribution")}</div>
        </Card>
      </div>
    </>
  );
}
