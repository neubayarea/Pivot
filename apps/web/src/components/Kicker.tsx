import type { ReactNode } from "react";

export default function Kicker({ children }: { children: ReactNode }) {
  return <span className="kicker">{children}</span>;
}
