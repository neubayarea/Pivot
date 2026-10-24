import type { ReactNode } from "react";

type Props = {
  tone: "live" | "ok" | "warn" | "bad" | "line";
  children: ReactNode;
};

export default function Stamp({ tone, children }: Props) {
  return <span className={`stamp ${tone}`}>{children}</span>;
}
