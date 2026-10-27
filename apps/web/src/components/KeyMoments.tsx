// The board's key moments (Ax38): goals, red cards, penalties and VAR reversals, under the
// numbered pivots. Picking one opens its clip under it (Ax42, rules in data/clips.ts) and leaves
// the main replay alone; "In the main replay" moves the replay there.
import { useEffect, useMemo } from "react";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { keyClip } from "../data/clips";
import { linkedPivot, type KeyKind, type KeyMoment, type Window } from "../data/keyMoments";
import { scrollBehavior } from "../data/motion";
import { useMatch, type Side } from "../data/match";
import { useT, type MessageKey, type T } from "../i18n";
import ClipPlayer, { KeyMark, usePeople } from "./ClipPlayer";

export { KeyMark };

/** ①, ②, ③: the badge a numbered pivot wears on the board. */
export const circled = (n: number) => (n >= 1 && n <= 20 ? String.fromCharCode(0x2460 + n - 1) : `(${n})`);

export const keyId = (k: KeyMoment) => k.event.event_id;

const Glyph = ({ kind, side }: { kind: KeyKind; side: Side }) => (
  <svg className="km-gl" viewBox="0 0 16 16" width={16} height={16} aria-hidden="true">
    <KeyMark kind={kind} side={side} x={8} y={8} size={1.1} />
  </svg>
);

/** What happened, in a line: "GOAL · Lisais", "Penalty to ROV · foul by Okafor". */
export function keyWhat(k: KeyMoment, t: T, playerName: (id: string | null) => string, team: (s: Side) => string): string {
  const who = playerName(k.event.player_id);
  switch (k.kind) {
    case "goal":
      return t(k.ownGoal ? "keys.ownGoal" : "keys.goal", { who });
    case "red":
      return t("event.red", { who });
    case "penalty":
      return t("keys.penalty", { team: team(k.side), who });
    case "var":
      return t("keys.var", { what: t(`keys.var.${k.event.var?.review_of ?? "goal"}` as MessageKey) });
  }
}

/** The legend under the momentum line, when it carries key marks as well as numbered pivots. */
export function KeyLegend({ kinds, pivots }: { kinds: ReadonlySet<KeyKind>; pivots: boolean }) {
  const t = useT();
  return (
    <p className="km-legend">
      {pivots && <span><b className="km-pv" aria-hidden="true">①</b> {t("keys.legendPivot")}</span>}
      {kinds.has("goal") && <span><Glyph kind="goal" side="home" /> {t("keys.legendGoal")}</span>}
      {kinds.has("red") && <span><Glyph kind="red" side="home" /> {t("keys.legendRed")}</span>}
      {(kinds.has("penalty") || kinds.has("var")) && <span><Glyph kind="var" side="home" /> {t("keys.legendOther")}</span>}
    </p>
  );
}

/** The moment played on the pitch, opened under it in the list; the main replay is left where it is. */
function KeyClip({ k }: { k: KeyMoment }) {
  const { match, events, playerName, teams, playback } = useMatch();
  const t = useT();
  const { clock } = useClock();
  const people = usePeople();
  const clip = useMemo(() => keyClip(k, events), [k, events]);
  const what = keyWhat(k, t, playerName, (s) => teams[s].short_name);
  const minute = k.event.clock_label.replace(/'$/, "′");
  const span = clip.parts.map(([a, b]) => `${clock(a)}–${clock(b)}`).join(", ");
  const show = () => {
    if (!playback) return;
    playback.setPlaying(false);
    playback.seek(k.event.t);
    window.scrollTo({ top: 0, behavior: scrollBehavior() });
  };
  const from = Math.max(0, Math.floor(clip.parts[0][0] / 60));
  return (
    <div className="km-clip">
      <ClipPlayer clip={clip} label={t("keys.clipLabel", { minute, what })} intro={t("keys.clipIntro")}>
        {clip.named && <p className="clip-chain"><b>{t(k.kind === "red" ? "keys.clipSentOff" : "keys.clipFoul")}</b> {people.tag(clip.named)}</p>}
        {k.kind === "goal" && clip.involved.length > 0 && (
          <p className="clip-chain"><b>{t("shots.involved")}</b> {clip.involved.map((id) => people.tag(id)).join(" → ")}</p>
        )}
        <p className="km-clip-ft">
          <small className="muted">{t(`keys.clipHow.${k.kind}` as MessageKey, { span })}</small>
          {playback
            ? <button type="button" className="btn ghost" onClick={show}>{t("keys.inMain")}</button>
            : <a href={`/?match=${encodeURIComponent(match.match_id)}&from=${from}`}>{t("keys.replayFrom")}</a>}
        </p>
      </ClipPlayer>
    </div>
  );
}

export default function KeyMoments({ moments, pivots, windows, selected, onPick, heading = true }: {
  moments: KeyMoment[];
  /** The board's numbered pivots, in order, and each one's evidence window (elapsed seconds). */
  pivots: Pivot[];
  windows: (p: Pivot) => Window | undefined;
  selected: string | null;
  /** The moment opened, or null to close it. */
  onPick: (id: string | null) => void;
  /** False when the page gives the list its own heading (the post-match tab). */
  heading?: boolean;
}) {
  const { teams, playerName } = useMatch();
  const t = useT();
  const linked = pivots.map((p) => ({ minute: p.minute, trigger_event_ids: p.trigger_event_ids, window: windows(p) }));
  // Picked from the momentum line, the moment may be out of sight.
  useEffect(() => {
    if (selected) document.getElementById(`km-${selected}`)?.scrollIntoView?.({ block: "nearest", behavior: scrollBehavior() });
  }, [selected]);
  return (
    <section className="keys" aria-labelledby={heading ? "keys-hd" : undefined} aria-label={heading ? undefined : t("keys.title")}>
      {heading && (
        <div className="keys-hd">
          <h2 id="keys-hd">{t("keys.title")}</h2>
          <p className="muted">{t("keys.note")}</p>
        </div>
      )}
      {!moments.length ? (
        <p className="muted">{t("keys.empty")}</p>
      ) : (
        <ol className="km-list">
          {moments.map((k) => {
            const what = keyWhat(k, t, playerName, (s) => teams[s].short_name);
            const minute = k.event.clock_label.replace(/'$/, "");
            const n = linkedPivot(k, linked);
            const big = k.situation && ["equaliser", "lateEqualiser", "stoppageEqualiser", "comeback", "winner"].includes(k.situation);
            return (
              <li key={keyId(k)} id={`km-${keyId(k)}`}>
                <button type="button" className={`km ${k.kind} to-${k.side}`} aria-expanded={keyId(k) === selected}
                  aria-label={t("keys.open", { minute, what })} onClick={() => onPick(keyId(k) === selected ? null : keyId(k))}>
                  <b className="km-min num">{minute}′</b>
                  <Glyph kind={k.kind} side={k.side} />
                  <span className="km-team">{teams[k.side].short_name}</span>
                  <span className="km-what">{what}</span>
                  <span className="km-tags">
                    {k.situation && <span className={`km-tag${big ? " big" : ""}`}>{t(`keys.sit.${k.situation}`)}</span>}
                    {k.penalty && <span className="km-tag">{t("keys.tagPenalty")}</span>}
                    {k.score && <span className="km-score num">{k.score.home}–{k.score.away}</span>}
                    {n > 0 && <span className="km-pv" title={t("keys.toPivotLabel", { n: circled(n) })}>{t("keys.toPivot", { n: circled(n) })}</span>}
                  </span>
                </button>
                {keyId(k) === selected && <KeyClip key={keyId(k)} k={k} />}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
