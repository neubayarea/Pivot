// Pass network (Bx12, Ax88): one side's starting eleven where they stood with the ball, and a line
// between two players who passed to each other. Drawn attacking to the right.
// - Fan: only the five pairs with the most passes, each line labelled with both names and the count,
//   the other players faded, and one sentence naming the pair who passed most.
// - Analyst: every pair with at least `min` passes (a slider, default 3), thickness and a number by
//   count, and the three most involved players (passes made plus received) ringed and listed.
// The report's edges are one direction each (A to B); here they are added up per pair.
import { useState } from "react";
import type { PassNetworkReport } from "@pivot/contracts";
import type { Side, SquadPlayer } from "../../data/view";
import { usePrefs } from "../../i18n";
import Segmented from "../Segmented";
import { VizPitch, teamColor, toPx, whoFrom } from "./pitch";
import "../../styles/viz.css";

export type NetPeriod = "all" | "1" | "2";
type Net = NonNullable<PassNetworkReport["teams"][string]>;

export type PassNetworkProps = {
  data: PassNetworkReport;
  side: Side;
  squads?: Record<Side, SquadPlayer[]>;
  teamNames?: Record<Side, string>;
  /** A player to ring, e.g. the one followed. */
  focus?: string | null;
  /** Analyst only: which half the report covers, and how to change it (the parent refetches). */
  period?: NetPeriod;
  onPeriod?: (p: NetPeriod) => void;
};

export const nodeRadius = (touches: number) => 9 + 1.3 * Math.sqrt(touches);
export const FAN_PAIRS = 5;
export const DEFAULT_MIN = 3;

export type Pair = { a: string; b: string; ab: number; ba: number; passes: number };

/** Edges added up per pair of players, most passes first (ties by id, so the order is stable). */
export function pairsOf(edges: Net["edges"]): Pair[] {
  const by = new Map<string, Pair>();
  for (const e of edges) {
    const [a, b] = e.from_id < e.to_id ? [e.from_id, e.to_id] : [e.to_id, e.from_id];
    const key = `${a}|${b}`;
    const p = by.get(key) ?? { a, b, ab: 0, ba: 0, passes: 0 };
    if (e.from_id === a) p.ab += e.passes;
    else p.ba += e.passes;
    p.passes += e.passes;
    by.set(key, p);
  }
  return [...by.values()].sort((x, y) => y.passes - x.passes || `${x.a}${x.b}`.localeCompare(`${y.a}${y.b}`));
}

/** The players most involved: passes made plus received, most first. */
export function hubsOf(nodes: Net["nodes"], n = 3) {
  return nodes.map((x) => ({ id: x.player_id, n: x.passes + x.received }))
    .filter((x) => x.n > 0).sort((x, y) => y.n - x.n || x.id.localeCompare(y.id)).slice(0, n);
}

type Box = { x: number; y: number; w: number; h: number };

/** Where to write each line's label: on the line if it is clear, else slid along it or nudged up or
 *  down, so two labels (or a label and a dot) do not sit on top of each other. Centres in pixels. */
export function placeLabels(lines: { x1: number; y1: number; x2: number; y2: number; w: number }[], dots: Box[], h = 16) {
  const taken: Box[] = [...dots];
  const overlap = (a: Box, b: Box) => Math.max(0, (a.w + b.w) / 2 - Math.abs(a.x - b.x)) * Math.max(0, (a.h + b.h) / 2 - Math.abs(a.y - b.y));
  return lines.map((l) => {
    let best: Box | null = null;
    let bestCost = Infinity;
    for (const f of [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8]) {
      for (const dy of [0, -h, h, -2 * h, 2 * h, -3 * h, 3 * h]) {
        const b = { x: l.x1 + (l.x2 - l.x1) * f, y: l.y1 + (l.y2 - l.y1) * f + dy, w: l.w + 6, h };
        // labels count more than dots: a covered dot still shows its edge, a covered label is lost
        const cost = taken.reduce((c, o, i) => c + overlap(o, b) * (i < dots.length ? 1 : 4), 0) + Math.abs(dy) * 0.5;
        if (cost < bestCost) { best = b; bestCost = cost; }
        if (cost === 0) break;
      }
      if (bestCost === 0) break;
    }
    taken.push(best!);
    return best!;
  });
}

/** "C. Dargorquina" -> "Dargorquina": the label on a line has room for a surname only. */
const surname = (name: string) => name.split(" ").filter(Boolean).slice(-1)[0] ?? name;

export default function PassNetwork({ data, side, squads, teamNames, focus = null, period = "all", onPeriod }: PassNetworkProps) {
  const { prefs, t } = usePrefs();
  const fan = prefs.audience === "fan";
  const [min, setMin] = useState(DEFAULT_MIN);
  const who = whoFrom(squads);
  const team = data.teams[side];
  const name = teamNames?.[side] ?? t(side === "home" ? "viz.home" : "viz.away");
  const at = new Map(team?.nodes.map((n) => [n.player_id, n]) ?? []);
  const all = pairsOf(team?.edges ?? []).filter((p) => at.has(p.a) && at.has(p.b));
  const maxMin = Math.max(DEFAULT_MIN, ...all.map((p) => p.passes));
  const shownMin = Math.min(min, maxMin);
  const pairs = fan ? all.slice(0, FAN_PAIRS) : all.filter((p) => p.passes >= shownMin);
  const most = Math.max(1, ...pairs.map((p) => p.passes));
  const inPairs = new Set(pairs.flatMap((p) => [p.a, p.b]));
  const hubs = fan ? [] : hubsOf(team?.nodes ?? []);
  const hubIds = new Set(hubs.map((h) => h.id));
  const top = all[0];
  const color = teamColor(side);
  const end = (id: string) => toPx(at.get(id)!.x, at.get(id)!.y);
  const texts = pairs.map((p) => fan
    ? t("viz.net.pairLabel", { a: surname(who(p.a).name), b: surname(who(p.b).name), n: p.passes }) : String(p.passes));
  const labels = placeLabels(pairs.map((p, i) => {
    const [x1, y1] = end(p.a);
    const [x2, y2] = end(p.b);
    return { x1, y1, x2, y2, w: texts[i].length * (fan ? 6.6 : 7.5) };
  }), (team?.nodes ?? []).map((n) => {
    const [x, y] = toPx(n.x, n.y);
    const d = 2 * nodeRadius(n.passes + n.received);
    return { x, y, w: d, h: d };
  }));
  return (
    <figure className="viz viz-net">
      <figcaption><b>{t("viz.net.title")}</b><span className={`viz-side ${side}`}>{name}</span></figcaption>
      {fan && top && (
        <p className="viz-net-most">{t("viz.net.most", { a: who(top.a).name, b: who(top.b).name, n: top.passes })}</p>
      )}
      {!fan && (
        <div className="viz-net-ctl">
          {onPeriod && (
            <Segmented label={t("viz.net.period")} value={period} onChange={onPeriod} options={[
              { value: "all", label: t("viz.net.full") },
              { value: "1", label: t("viz.net.h1") },
              { value: "2", label: t("viz.net.h2") },
            ]} />
          )}
          <label className="viz-net-min">
            <span>{t("viz.net.min")}</span>
            <input type="range" min={1} max={maxMin} step={1} value={shownMin} onChange={(e) => setMin(Number(e.target.value))} />
            <b className="num">{shownMin}</b>
          </label>
        </div>
      )}
      <VizPitch label={t("viz.net.label", { team: name })} arrow>
        {pairs.map((p) => {
          const [x1, y1] = end(p.a);
          const [x2, y2] = end(p.b);
          return (
            <line key={`${p.a}-${p.b}`} className="viz-edge" x1={x1} y1={y1} x2={x2} y2={y2} stroke={color}
              strokeWidth={1.5 + 7 * (p.passes / most)} strokeOpacity={0.3 + 0.45 * (p.passes / most)} strokeLinecap="round">
              <title>{t("viz.net.pairTip", { a: who(p.a).name, b: who(p.b).name, ab: p.ab, ba: p.ba })}</title>
            </line>
          );
        })}
        {team?.nodes.map((n) => {
          const [x, y] = toPx(n.x, n.y);
          const p = who(n.player_id);
          const r = nodeRadius(n.passes + n.received);
          const faded = fan && pairs.length > 0 && !inPairs.has(n.player_id);
          const isFocus = n.player_id === focus;
          return (
            <g key={n.player_id} className={`viz-node${isFocus ? " on" : ""}${faded ? " faded" : ""}`}>
              <title>{t(fan ? "viz.net.tipFan" : "viz.net.tip", { name: p.name, passes: n.passes, received: n.received })}</title>
              {hubIds.has(n.player_id) && <circle className="viz-hub" cx={x} cy={y} r={r + 5} />}
              <circle cx={x} cy={y} r={r} fill={color} stroke={isFocus ? "var(--pv-gold)" : "var(--pv-paper)"}
                strokeWidth={isFocus ? 4 : 2} />
              <text x={x} y={y + 4.5} textAnchor="middle" fontSize={13} fontWeight={700} fill="var(--pv-paper)">{p.shirt}</text>
            </g>
          );
        })}
        {/* the counts go on last, so no dot covers them */}
        {labels.map((l, i) => (
          <text key={`n-${pairs[i].a}-${pairs[i].b}`} className={`viz-edge-n${fan ? " fan" : ""}`} x={l.x} y={l.y + 4}
            textAnchor="middle" aria-hidden="true">{texts[i]}</text>
        ))}
      </VizPitch>
      {!team?.nodes.length && <p className="viz-empty">{t("viz.net.empty")}</p>}
      {!fan && hubs.length > 0 && (
        <div className="viz-net-hubs">
          <b>{t("viz.net.hubs")}</b>
          <ol>
            {hubs.map((h) => (
              <li key={h.id}>
                <b className={`viz-shirt ${side}`}>{who(h.id).shirt}</b>{who(h.id).name}
                <span className="num">{t("viz.net.hubN", { n: h.n })}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {/* names under the pitch: on it they run into each other where the midfield is crowded */}
      <ol className="viz-names">
        {[...(team?.nodes ?? [])].sort((a, b) => Number(who(a.player_id).shirt) - Number(who(b.player_id).shirt)).map((n) => (
          <li key={n.player_id} className={n.player_id === focus ? "on" : undefined}>
            <b className={`viz-shirt ${side}`}>{who(n.player_id).shirt}</b>{who(n.player_id).name}
          </li>
        ))}
      </ol>
      <p className="viz-note">
        {fan ? <>{t("viz.net.legendFan")} {t("viz.net.legendTop")}</>
          : <>{t("viz.net.legend", { min: shownMin })} {hubs.length > 0 && t("viz.net.legendHubs")}</>}
      </p>
    </figure>
  );
}
