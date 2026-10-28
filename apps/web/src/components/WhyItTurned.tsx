import { Fragment, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import type { Claim, Pivot1 as Pivot } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { involves, useMatch } from "../data/match";
import { useLocalising } from "../data/view";
import { isMessageKey, narrativeLang, usePrefs, type MessageKey, type T } from "../i18n";
import Card from "./Card";
import { surname } from "./FocusPickers";
import { WorkingDots } from "./Skeleton";
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

const near = (a: number, b: number) => Math.abs(a - b) < 0.051;
const sameStat = (a: Claim, b: Claim) =>
  a.stat_ref.metric === b.stat_ref.metric && a.stat_ref.team === b.stat_ref.team && a.stat_ref.player_id === b.stat_ref.player_id;

/**
 * Which claims a highlighted figure ("0 to 5") was read from (#332): the claim whose value is the
 * figure's last number, preferring one with a same-stat partner holding the first number ("from").
 * Claims already given to an earlier figure are skipped; when no value matches, the next unused
 * claim in order is used, as before.
 */
export function claimsFor(figure: string, claims: Claim[], used: Set<number>): { to: Claim; from?: Claim } | null {
  const nums = (figure.match(/\d+(?:\.\d+)?/g) ?? []).map(Number);
  const free = claims.map((c, j) => [c, j] as const).filter(([, j]) => !used.has(j));
  if (!free.length) return claims.length ? { to: claims[claims.length - 1] } : null;
  const first = nums[0];
  const last = nums[nums.length - 1];
  const partner = (c: Claim, j: number) =>
    nums.length > 1 ? free.find(([d, h]) => h !== j && sameStat(d, c) && near(d.value, first)) : undefined;
  const to =
    (last !== undefined && free.find(([c, j]) => near(c.value, last) && partner(c, j))) ||
    (last !== undefined && free.find(([c]) => near(c.value, last))) ||
    free.find(([c]) => nums.some((x) => near(c.value, x))) ||
    free[0];
  const from = partner(to[0], to[1]);
  used.add(to[1]);
  if (from) used.add(from[1]);
  return { to: to[0], from: from?.[0] };
}

function Highlighted({ text, claims, name }: { text: string; claims: Claim[]; name: RegExp | null }) {
  const used = new Set<number>();
  return (
    <>
      {text.split(FIGURE).map((part, i) => {
        if (!(i % 2)) return <Named key={i} text={part} name={name} />;
        const src = claimsFor(part, claims, used);
        return src ? (
          <Sourced key={i} claim={src.to} from={src.from} className="hl">
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

/** An event's kind in the viewer's words, for the evidence chips ("Evidence · Pass #260"). */
const kindOf = (type: string, t: T) => {
  const k = `event.type.${type}`;
  return isMessageKey(k) ? t(k) : type[0].toUpperCase() + type.slice(1).replaceAll("_", " ");
};

export default function WhyItTurned({ pivot, selected, onToggle, chipHint, outside }: Props) {
  const { eventById, playerName } = useMatch();
  const { prefs, t } = usePrefs();
  const { minute } = useClock();
  const localising = useLocalising();
  const focus = prefs.focus_player_id;
  const name = nameMatcher(playerName(focus));
  const narrative = pivot?.narrative;
  const { search } = useLocation();
  // Fans get the sentences without the evidence numbers (#904); a tap on a sentence's sources
  // shows them. Analysts always see them (Ax59, #276).
  const fan = prefs.audience === "fan";
  const [opened, setOpened] = useState<ReadonlySet<number>>(new Set());
  // The sentence whose sources were just shown: its first chip takes the focus the button had.
  const [justOpened, setJustOpened] = useState<number | null>(null);
  // Ax79: the version on screen (whose, in which language). When the fan version or the translation
  // that was being written arrives, its sentences fade in where the analyst text was.
  const version = narrative ? `${pivot?.pivot_id}:${narrative.prefs.audience}:${narrativeLang(narrative) ?? ""}:${narrative.sentences.length}` : "";
  const [first, setFirst] = useState({ pivot: pivot?.pivot_id, version });
  if (first.pivot !== pivot?.pivot_id) setFirst({ pivot: pivot?.pivot_id, version });
  const arrived = first.pivot === pivot?.pivot_id && version !== first.version;
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
    <Card title={t("why.title")} note={t(auto ? "why.noteAuto" : "why.noteVerified", { minute: minute(pivot.minute) })} className="why drop">
      {(fellBack || plainForFan) && (
        // A div, not a p: the drop cap goes on the first paragraph of the explanation.
        <div className={`lang-note${localising ? " writing" : ""}`} role={localising ? "status" : "note"}>
          {t(noteKey(fellBack, plainForFan, localising), vars)}
          {localising && <WorkingDots />}
        </div>
      )}
      {narrative.sentences.map((s, i) => (
        <p key={`${version}:${i}`} lang={fellBack ? served : undefined} className={arrived ? "ph-in" : undefined}>
          <Highlighted text={s.text} claims={s.claims} name={name} />
          {fan && s.evidence_ids.length > 0 && !opened.has(i) ? (
            <>
              {" "}
              <button type="button" className="ev-more" aria-expanded={false}
                onClick={() => (setOpened(new Set(opened).add(i)), setJustOpened(i))}>
                {t("why.sources", { n: s.evidence_ids.length })}
              </button>
            </>
          ) : s.evidence_ids.map((id, k) => {
            const e = eventById(id);
            // ★ marks the evidence the followed player took part in.
            const star = !!e && involves(e, focus);
            const out = !!outside?.has(id);
            return (
              <Fragment key={id}>
                {" "}
                {!fan && e && <span className="ev-kind">{t("why.evKind", { kind: kindOf(e.type, t) })}</span>}
                <button type="button" className={`ev${selected.has(id) ? " on" : ""}${star ? " star" : ""}${out ? " out" : ""}`}
                  ref={k === 0 && justOpened === i ? (el) => el?.focus() : undefined}
                  aria-pressed={selected.has(id)} title={chipHint ?? t("why.chipHint")} onClick={() => onToggle(id)}>
                  {star && "★ "}#{e?.seq ?? id}
                  {out && <span className="ev-out"> {t("why.outside")}</span>}
                </button>
              </Fragment>
            );
          })}
        </p>
      ))}
      {/* C18 (#366): the evidence is checkable: the AI's steps for this turning point, in the work log. */}
      {!fan && pivot && <Link className="ev-trace" to={`/trace/${pivot.pivot_id}${search}`}>{t("why.checkTrace")} <span aria-hidden="true">↗</span></Link>}
      <span className="pipe">
        {t(auto ? "why.pipeAuto" : "why.pipeOk")} {t("why.counts", { claims, evidence })}
      </span>
    </Card>
  );
}
