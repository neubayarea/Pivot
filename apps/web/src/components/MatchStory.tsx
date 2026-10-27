// The story of the match (C12, #311): the fan's first block on the post-match tab. Three or four
// big cards in time order, each one sentence and one picture: the AI's turning points with the run
// of play around them, and the goals and red cards, each playable as a clip (ClipPlayer). With a ♥
// team each card says whether it went your way, in the kit colours (never yellow, which is the AI's).
import { useMemo, useState, type CSSProperties } from "react";
import type { MinuteMetric, Pivot1 as Pivot } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { keyClip } from "../data/clips";
import { keyMoments, type KeyMoment } from "../data/keyMoments";
import { useMatch, type Side } from "../data/match";
import { lean, usePersona, type Lean } from "../data/persona";
import { useT } from "../i18n";
import ClipPlayer from "./ClipPlayer";
import { keyWhat } from "./KeyMoments";
import { pivotHeadline } from "./PivotList";

type Item = { id: string; t: number; side: Side; pivot?: Pivot; n?: number; key?: KeyMoment; also?: KeyMoment[] };

/**
 * Up to `max` items: every turning point first, then goals (decisive ones first) and red cards, in time order.
 * A goal or red card that set a turning point off, or came within a minute of it, is a line on that
 * turning point's card (`also`), not a card of its own (C13 QA: 35′ was told twice).
 */
export function storyItems(pivots: readonly Pivot[], keys: readonly KeyMoment[], max = 4): Item[] {
  const moments = pivots.filter((p) => p.status === "confirmed" || p.status === "degraded").sort((a, b) => a.minute - b.minute);
  const weight = (k: KeyMoment) => (k.kind === "goal" ? (k.situation && k.situation !== "opener" ? 3 : 2) : k.kind === "red" ? 1 : 0);
  const big = keys.filter((k) => weight(k) > 0).sort((a, b) => a.event.t - b.event.t);
  const host = (k: KeyMoment) => moments.find((p) => p.trigger_event_ids.includes(k.event.event_id))
    ?? moments.find((p) => Math.abs(k.event.t / 60 - p.minute) <= 1);
  const also = new Map<string, KeyMoment[]>();
  const loose: KeyMoment[] = [];
  for (const k of big) {
    const p = host(k);
    if (p) also.set(p.pivot_id, [...(also.get(p.pivot_id) ?? []), k]);
    else loose.push(k);
  }
  const items: Item[] = moments.map((p, i) => ({ id: p.pivot_id, t: p.minute * 60, side: p.direction, pivot: p, n: i + 1, also: also.get(p.pivot_id) }));
  const extra = loose.sort((a, b) => weight(b) - weight(a) || a.event.t - b.event.t);
  for (const k of extra) {
    if (items.length >= max) break;
    items.push({ id: k.event.event_id, t: k.event.t, side: k.side, key: k });
  }
  return items.slice(0, max).sort((a, b) => a.t - b.t);
}

/** The run of play eight minutes either side of a turning point, in the two kit colours. */
function Swing({ metrics, minute }: { metrics: readonly MinuteMetric[]; minute: number }) {
  const pts = metrics.filter((m) => Math.abs(m.minute - minute) <= 8);
  if (pts.length < 3) return null;
  const W = 240, H = 64, x = (m: number) => ((m - (minute - 8)) / 16) * W, y = (v: number) => H / 2 - v * (H / 2 - 2);
  const area = `M${x(pts[0].minute)},${H / 2} ${pts.map((p) => `L${x(p.minute)},${y(p.momentum)}`).join(" ")} L${x(pts.at(-1)!.minute)},${H / 2} Z`;
  return (
    <svg className="story-swing" viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
      <clipPath id={`st-up-${minute}`}><rect width={W} height={H / 2} /></clipPath>
      <clipPath id={`st-dn-${minute}`}><rect y={H / 2} width={W} height={H / 2} /></clipPath>
      <path d={area} fill="var(--pv-home)" clipPath={`url(#st-up-${minute})`} />
      <path d={area} fill="var(--pv-away)" clipPath={`url(#st-dn-${minute})`} />
      <line x1={x(minute)} x2={x(minute)} y1={0} y2={H} stroke="var(--pv-ink)" strokeWidth={1.5} />
    </svg>
  );
}

export default function MatchStory() {
  const { match, teams, pivots, events, metrics, playerName } = useMatch();
  const t = useT();
  const { minute } = useClock();
  const { side } = usePersona();
  const [open, setOpen] = useState<string | null>(null);
  const items = useMemo(() => storyItems(pivots, keyMoments(events, match.status === "finished")), [pivots, events, match.status]);
  const opened = items.flatMap((i) => (i.key ? [i.key] : i.also ?? [])).find((k) => k.event.event_id === open);
  const clip = useMemo(() => (opened ? keyClip(opened, events) : null), [opened, events]);
  if (!items.length) return <p className="muted">{t("story.empty")}</p>;
  const leanOf = (s: Side): Lean => lean({ direction: s }, side);
  const what = (k: KeyMoment) => keyWhat(k, t, playerName, (s) => teams[s].short_name);
  const watch = (id: string) => (
    <button type="button" className="btn story-watch" aria-expanded={open === id} onClick={() => setOpen(open === id ? null : id)}>
      {t(open === id ? "story.close" : "story.watch")}
    </button>
  );

  return (
    <div className="story">
      <ol className="story-cards">
        {items.map((it) => {
          const l = leanOf(it.side);
          const label = it.pivot
            ? pivotHeadline(it.pivot, teams, t)
            : what(it.key!);
          const at = it.pivot ? `${minute(it.pivot.minute)}′` : it.key!.event.clock_label.replace(/'/g, "′");
          return (
            <li key={it.id} className={`story-card${it.pivot ? " pivot" : ""}${l ? ` ${l}` : ""}`} style={{ "--tc": `var(--pv-${it.side})` } as CSSProperties}>
              <span className="story-min num">
                {it.pivot && <span className="badge" aria-hidden="true">{it.n}</span>}
                {at}
              </span>
              <p className="story-what">{label}</p>
              {it.pivot ? (
                <>
                  <Swing metrics={metrics} minute={it.pivot.minute} />
                  <p className="muted story-sub">{t("story.turn", { team: teams[it.side].name })}</p>
                  {it.also?.map((k) => (
                    <div key={k.event.event_id} className="story-also">
                      <p><span className="num">{k.event.clock_label.replace(/'/g, "′")}</span> {what(k)}</p>
                      {watch(k.event.event_id)}
                    </div>
                  ))}
                </>
              ) : (
                watch(it.id)
              )}
              {l && <span className={`story-lean ${l}`}>{t(l === "for" ? "you.for" : "you.against")}</span>}
            </li>
          );
        })}
      </ol>
      {opened && clip && (
        <div className="story-clip">
          <ClipPlayer clip={clip} label={what(opened)} intro={t("keys.clipIntro")} />
        </div>
      )}
    </div>
  );
}
