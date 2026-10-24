import type { ReactNode } from "react";
import Card from "./Card";

type Props = {
  title: string;
  children: ReactNode;
  /** The next step: buttons or links. */
  actions?: ReactNode;
  tone?: "info" | "error";
};

/** One centred card that says what happened and what to do next, for pages with nothing else to show. */
export default function StateCard({ title, children, actions, tone = "info" }: Props) {
  return (
    <div className="state-page">
      <Card title={title} className={`state-card ${tone}`}>
        <div role={tone === "error" ? "alert" : undefined}>{children}</div>
        {actions && <div className="state-actions">{actions}</div>}
      </Card>
    </div>
  );
}
