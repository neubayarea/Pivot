import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import StateCard from "../components/StateCard";
import { useT } from "../i18n";

type Props = { title?: string; children?: ReactNode };

export default function NotFound({ title, children }: Props) {
  const t = useT();
  return (
    <StateCard title={title ?? t("notFound.title")} actions={<Link className="btn pri" to="/">{t("notFound.back")}</Link>}>
      {children ?? <p>{t("notFound.body")}</p>}
    </StateCard>
  );
}
