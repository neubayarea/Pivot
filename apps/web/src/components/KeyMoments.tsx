// The board's key moments (Ax38): goals, red cards, penalties and VAR reversals, under the
// numbered pivots. Picking one moves the replay there (and the pitch with it); a match that is
// not being replayed shows the pitch at that second and offers a replay from just before it.
import { useMemo, useState } from "react";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { useFrames } from "../data/live/frames";
import { linkedPivot, type KeyKind, type KeyMoment, type Window } from "../data/keyMoments";
import { fixtureMode, useMatch, type Side } from "../data/match";
import { useT, type MessageKey, type T } from "../i18n";
import Pitch, { whoFromSquads } from "./Pitch";

/** ①, ②, ③: the badge a numbered pivot wears on the board. */
export const circled = (n: number) => (n >= 1 && n <= 20 ? String.fromCharCode(0x2460 + n - 1) : `(${n})`);

export const keyId = (k: KeyMoment) => k.event.event_id;

/** The small mark for a key moment, centred on (x, y): a ball for a goal, a card for a red, a diamond otherwise. */
export function KeyMark({ kind, side, x, y, size = 1 }: { kind: KeyKind; side: Side; x: number; y: number; size?: number }) {
  if (kind === "goal") {
    return <circle cx={x} cy={y} r={5.5 * size} fill={side === "home" ? "var(--pv-home)" : "var(--pv-away)"} stroke="var(--pv-ink)" strokeWidth={1.5} />;
  }
  if (kind === "red") {
    return <rect x={x - 3.5 * size} y={y - 5 * size} width={7 * size} height={10 * size} fill="var(--pv-red)" stroke="var(--pv-ink)" strokeWidth={1.5} />;
  }
  const d = 5.5 * size;
  return <path d={`M${x},${y - d} L${x + d},${y} L${x},${y + d} L${x - d},${y} Z`} fill="var(--pv-sheet)" stroke="var(--pv-ink)" strokeWidth={1.5} />;
}

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

/** Where everyone stood at the moment, for a match that is not being replayed. */
function KeyPitch({ k }: { k: KeyMoment }) {
  const { match, squads, playerName, teams } = useMatch();
  const t = useT();
  const { frame, missing } = useFrames(match.match_id, k.event.t);
  const who = useMemo(() => whoFromSquads(squads), [squads]);
  if (missing) return null;
  const from = Math.max(0, Math.floor(k.event.t / 60) - 1);
  return (
    <figure className="km-pitch">
      {frame
        ? <Pitch frame={frame} actions={k.event.location ? [k.event] : []} selected={k.event.event_id} focus={null} who={who}
            label={t("detail.pitchLabel", { t: frame.t, n: frame.players.length })} />
        : <div className="empty-box muted">{t("board.pitchLoading")}</div>}
      <figcaption>
        <b>{k.event.clock_label.replace(/'$/, "′")}</b> {keyWhat(k, t, playerName, (s) => teams[s].short_name)}
        {" · "}<a href={`/?match=${encodeURIComponent(match.match_id)}&from=${from}`}>{t("keys.replayFrom")} →</a>
      </figcaption>
    </figure>
  );
}

export default function KeyMoments({ moments, pivots, windows, selected, onPick }: {
  moments: KeyMoment[];
  /** The board's numbered pivots, in order, and each one's evidence window (elapsed seconds). */
  pivots: Pivot[];
  windows: (p: Pivot) => Window | undefined;
  selected: string | null;
  onPick: (id: string) => void;
}) {
  const { teams, playerName, playback } = useMatch();
  const t = useT();
  const [fixture] = useState(() => typeof window === "undefined" || fixtureMode());
  const linked = pivots.map((p) => ({ minute: p.minute, trigger_event_ids: p.trigger_event_ids, window: windows(p) }));
  const open = moments.find((k) => keyId(k) === selected);
  return (
    <section className="keys" aria-labelledby="keys-hd">
      <div className="keys-hd">
        <h2 id="keys-hd">{t("keys.title")}</h2>
        <p className="muted">{t("keys.note")}</p>
      </div>
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
              <li key={keyId(k)}>
                <button type="button" className={`km ${k.kind} to-${k.side}`} aria-pressed={keyId(k) === selected}
                  aria-label={t("keys.open", { minute, what })} onClick={() => onPick(keyId(k))}>
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
              </li>
            );
          })}
        </ol>
      )}
      {open && !playback && !fixture && <KeyPitch key={keyId(open)} k={open} />}
    </section>
  );
}
