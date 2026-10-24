import type { ReactNode } from "react";

type Props = {
  title: string;
  note?: ReactNode;
  className?: string;
  children?: ReactNode;
};

export default function Card({ title, note, className = "", children }: Props) {
  return (
    <section className={`card ${className}`.trim()}>
      <h3>
        {title}
        {note && <small>{note}</small>}
      </h3>
      {children}
    </section>
  );
}
