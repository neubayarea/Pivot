import { Fragment } from "react";
import type { Claim, Pivot1 as Pivot } from "@pivot/contracts";
import { useMatch } from "../data/match";
import Card from "./Card";
import Sourced from "./Sourced";

// Numbers the verifier checked ("9 to 3", "6 of 8", "48% to 61%") get the highlighter.
const FIGURE = /(\d+(?:\.\d+)?%? (?:to|of) \d+(?:\.\d+)?%?)/;

function Highlighted({ text, claims }: { text: string; claims: Claim[] }) {
  return (
    <>
      {text.split(FIGURE).map((part, i) => {
        if (!(i % 2)) return <Fragment key={i}>{part}</Fragment>;
        // Figures and claims line up in order; extra figures share the sentence's last claim.
        const claim = claims[Math.min((i - 1) / 2, claims.length - 1)];
        return claim ? (
          <Sourced key={i} claim={claim} className="hl">
            {part}
          </Sourced>
        ) : (
          <span key={i} className="hl">
            {part}
          </span>
        );
      })}
    </>
  );
}

type Props = {
  pivot: Pivot | null;
  selected: ReadonlySet<string>;
  onToggle: (eventId: string) => void;
  /** What clicking an evidence chip does, for its tooltip. */
  chipHint?: string;
};

export default function WhyItTurned({ pivot, selected, onToggle, chipHint = "Highlight this event in the feed" }: Props) {
  const { eventById } = useMatch();
  const narrative = pivot?.narrative;
  if (!pivot || !narrative) {
    return (
      <Card title="Why it turned" className="why">
        <p className="muted">The verified explanation for the latest pivot appears here.</p>
      </Card>
    );
  }
  const claims = narrative.sentences.reduce((n, s) => n + s.claims.length, 0);
  const evidence = new Set(narrative.sentences.flatMap((s) => s.evidence_ids)).size;
  const auto = pivot.status === "degraded";
  return (
    <Card title="Why it turned" note={`${pivot.minute}′ · ${auto ? "auto summary" : "verified"}`} className="why drop">
      {narrative.sentences.map((s, i) => (
        <p key={i}>
          <Highlighted text={s.text} claims={s.claims} />
          {s.evidence_ids.map((id) => (
            <Fragment key={id}>
              {" "}
              <button type="button" className={`ev${selected.has(id) ? " on" : ""}`} aria-pressed={selected.has(id)}
                title={chipHint} onClick={() => onToggle(id)}>
                #{eventById(id)?.seq ?? id}
              </button>
            </Fragment>
          ))}
        </p>
      ))}
      <span className="pipe">
        {auto ? "Judge ✓ · AI explanation delayed · automatic summary" : "Judge ✓ · Explainer ✓ · Verifier ✓"}{" "}
        {claims} claims · {evidence} evidence
      </span>
    </Card>
  );
}
