import { Fragment } from "react";
import type { Claim, Pivot1 as Pivot } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { involves, useMatch } from "../data/match";
import { useLocalising } from "../data/view";
import { narrativeLang, usePrefs, type MessageKey } from "../i18n";
import Card from "./Card";
import { surname } from "./FocusPickers";
import Sourced from "./Sourced";

// Numbers the verifier checked get the highlighter: "9 to 3", "6 of 8", "48% to 61%"; in Spanish
// "de 9 a 3", "del 48% al 61%", "6 de 8"; in Chinese "从 9 次降到 3 次", "8 战 6 胜", "16 次中有 14 次".
const FIGURE =
  /(\d+(?:\.\d+)?%? ?(?:to|of|a|al|de|次?(?:升到|降到|增至|减至|到)|战|次中有) ?\d+(?:\.\d+)?%?)/;

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Matches the followed player's full name or surname as a whole word; null when none is followed. */
export function nameMatcher(name: string): RegExp | null {
  if (!name) return null;
  const forms = [...new Set([name, surname(name)])].map(escape).join("|");
  return new RegExp(`((?<!\\p{L})(?:${forms})(?!\\p{L}))`, "u");
}

/** The followed player's name gets the gold highlighter, like the checked figures. */
function Named({ text, name }: { text: string; name: RegExp | null }) {
  if (!name) return <>{text}</>;
  return (
    <>
      {text.split(name).map((part, i) => (i % 2 ? <span key={i} className="hl who">{part}</span> : <Fragment key={i}>{part}</Fragment>))}
    </>
  );
}

function Highlighted({ text, claims, name }: { text: string; claims: Claim[]; name: RegExp | null }) {
  return (
    <>
      {text.split(FIGURE).map((part, i) => {
        if (!(i % 2)) return <Named key={i} text={part} name={name} />;
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

/** The note over an explanation that is not the one asked for: another language, the analyst version, or both. */
function noteKey(otherLang: boolean, analystForFan: boolean, writing: boolean): MessageKey {
  if (!analystForFan) return writing ? "why.writing" : "why.fallback";
  if (otherLang) return writing ? "why.fanWritingLang" : "why.fanFallbackLang";
  return writing ? "why.fanWriting" : "why.fanFallback";
}

type Props = {
  pivot: Pivot | null;
  selected: ReadonlySet<string>;
  onToggle: (eventId: string) => void;
  /** What clicking an evidence chip does, for its tooltip. */
  chipHint?: string;
  /** Evidence outside the pitch timeline (S2): its chip says so, since it has no tick to jump to. */
  outside?: ReadonlySet<string>;
};

export default function WhyItTurned({ pivot, selected, onToggle, chipHint, outside }: Props) {
  const { eventById, playerName } = useMatch();
  const { prefs, t } = usePrefs();
  const { minute } = useClock();
  const localising = useLocalising();
  const focus = prefs.focus_player_id;
  const name = nameMatcher(playerName(focus));
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
  // Likewise the analyst version while the fan one is written (or when it could not be).
  const plainForFan = prefs.audience === "fan" && narrative.prefs.audience !== "fan";
  const vars = { wanted: t(`lang.${prefs.language}`), served: t(`lang.${served ?? "en"}`) };
  return (
    <Card title={t("why.title")} note={`${minute(pivot.minute)}′ · ${t(auto ? "why.noteAuto" : "why.noteVerified")}`} className="why drop">
      {(fellBack || plainForFan) && (
        // A div, not a p: the drop cap goes on the first paragraph of the explanation.
        <div className="lang-note" role="note">
          {t(noteKey(fellBack, plainForFan, localising), vars)}
        </div>
      )}
      {narrative.sentences.map((s, i) => (
        <p key={i} lang={fellBack ? served : undefined}>
          <Highlighted text={s.text} claims={s.claims} name={name} />
          {s.evidence_ids.map((id) => {
            const e = eventById(id);
            // ★ marks the evidence the followed player took part in.
            const star = !!e && involves(e, focus);
            const out = !!outside?.has(id);
            return (
              <Fragment key={id}>
                {" "}
                <button type="button" className={`ev${selected.has(id) ? " on" : ""}${star ? " star" : ""}${out ? " out" : ""}`}
                  aria-pressed={selected.has(id)} title={chipHint ?? t("why.chipHint")} onClick={() => onToggle(id)}>
                  {star && "★ "}#{e?.seq ?? id}
                  {out && <span className="ev-out"> · {t("why.outside")}</span>}
                </button>
              </Fragment>
            );
          })}
        </p>
      ))}
      <span className="pipe">
        {t(auto ? "why.pipeAuto" : "why.pipeOk")} {t("why.counts", { claims, evidence })}
      </span>
    </Card>
  );
}
