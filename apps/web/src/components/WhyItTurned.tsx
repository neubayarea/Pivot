import { Fragment } from "react";
import type { Claim, Pivot1 as Pivot } from "@pivot/contracts";
import { useMatch } from "../data/match";
import { narrativeLang, usePrefs } from "../i18n";
import Card from "./Card";
import Sourced from "./Sourced";

// Numbers the verifier checked get the highlighter: "9 to 3", "6 of 8", "48% to 61%"; in Spanish
// "de 9 a 3", "del 48% al 61%", "6 de 8"; in Chinese "从 9 次降到 3 次", "8 战 6 胜", "16 次中有 14 次".
const FIGURE =
  /(\d+(?:\.\d+)?%? ?(?:to|of|a|al|de|次?(?:升到|降到|增至|减至|到)|战|次中有) ?\d+(?:\.\d+)?%?)/;

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

export default function WhyItTurned({ pivot, selected, onToggle, chipHint }: Props) {
  const { eventById } = useMatch();
  const { prefs, t } = usePrefs();
  const narrative = pivot?.narrative;
  if (!pivot || !narrative) {
    return (
      <Card title={t("why.title")} className="why">
        <p className="muted">{t("why.empty")}</p>
      </Card>
    );
  }
  const claims = narrative.sentences.reduce((n, s) => n + s.claims.length, 0);
  const evidence = new Set(narrative.sentences.flatMap((s) => s.evidence_ids)).size;
  const auto = pivot.status === "degraded";
  // The API writes English when it cannot write the asked language; say so instead of hiding it.
  const served = narrativeLang(narrative);
  const fellBack = served !== null && served !== prefs.language;
  return (
    <Card title={t("why.title")} note={`${pivot.minute}′ · ${t(auto ? "why.noteAuto" : "why.noteVerified")}`} className="why drop">
      {fellBack && (
        // A div, not a p: the drop cap goes on the first paragraph of the explanation.
        <div className="lang-note" role="note">
          {t("why.fallback", { wanted: t(`lang.${prefs.language}`), served: t(`lang.${served}`) })}
        </div>
      )}
      {narrative.sentences.map((s, i) => (
        <p key={i}>
          <Highlighted text={s.text} claims={s.claims} />
          {s.evidence_ids.map((id) => (
            <Fragment key={id}>
              {" "}
              <button type="button" className={`ev${selected.has(id) ? " on" : ""}`} aria-pressed={selected.has(id)}
                title={chipHint ?? t("why.chipHint")} onClick={() => onToggle(id)}>
                #{eventById(id)?.seq ?? id}
              </button>
            </Fragment>
          ))}
        </p>
      ))}
      <span className="pipe">
        {t(auto ? "why.pipeAuto" : "why.pipeOk")} {t("why.counts", { claims, evidence })}
      </span>
    </Card>
  );
}
