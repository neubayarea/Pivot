import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import StateCard from "../components/StateCard";

type Props = { title?: string; children?: ReactNode };

export default function NotFound({ title = "Page not found", children }: Props) {
  return (
    <StateCard title={title} actions={<Link className="btn pri" to="/">← Back to the live board</Link>}>
      {children ?? <p>There is nothing at this address. The link may be mistyped or from an older version.</p>}
    </StateCard>
  );
}
