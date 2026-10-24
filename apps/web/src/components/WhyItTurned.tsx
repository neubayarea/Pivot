import { Fragment } from "react";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { useMatch } from "../data/match";
import Card from "./Card";

// Numbers the verifier checked ("9 to 3", "6 of 8", "48% to 61%") get the highlighter.
const FIGURE = /(\d+(?:\.\d+)?%? (?:to|of) \d+(?:\.\d+)?%?)/;

function Highlighted({ text }: { text: string }) {
  return (
    <>
      {text.split(FIGURE).map((part, i) =>
        i % 2 ? (
          <span key={i} className="hl">
            {part}
          </span>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

type Props = {
  pivot: Pivot | null;
  selected: ReadonlySet<string>;
  onToggle: (eventId: string) => void;
};

export default function WhyItTurned({ pivot, selected, onToggle }: Props) {
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
  return (
    <Card title="Why it turned" note={`${pivot.minute}′ · verified`} className="why drop">
      {narrative.sentences.map((s, i) => (
        <p key={i}>
          <Highlighted text={s.text} />
          {s.evidence_ids.map((id) => (
            <Fragment key={id}>
              {" "}
              <button type="button" className={`ev${selected.has(id) ? " on" : ""}`} aria-pressed={selected.has(id)}
                title="Highlight this event in the feed" onClick={() => onToggle(id)}>
                #{eventById(id)?.seq ?? id}
              </button>
            </Fragment>
          ))}
        </p>
      ))}
      <span className="pipe">
        Judge ✓ · Explainer ✓ · Verifier ✓ {claims} claims · {evidence} evidence
      </span>
    </Card>
  );
}
