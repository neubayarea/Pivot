import { useMemo, useState } from "react";
import type { MatchEvent, TrackingFrame } from "@pivot/contracts";
import { fixtureMode, useMatch } from "../data/match";
import { useFrames, useFrameWindow } from "../data/live/frames";
import { minuteAt, minuteLabel, PLAIN_PERIODS } from "../data/clock";
import { isRedCard, type Side, type SquadPlayer } from "../data/view";
import { useT, type MessageKey } from "../i18n";
import Card from "./Card";
import { describe } from "./EventFeed";
import Pitch, { whoFromSquads } from "./Pitch";
import { backLineX, frameShape, lineOf, lineupAt, meanShape, shapeLines, type Lineup, type Role, type Shape } from "./shape";
import "../styles/pitch-board.css";

// A shot stays drawn this many seconds after it was taken.
const SHOT_FOR = 3;
// The dots glide at least this long between frames, so fast replays still look like movement.
const MIN_STEP_MS = 250;
// The players in an event keep their ring this long after it.
const MARK_FOR = 8;
// For this long after a pivot its evidence players stay marked and the shape is compared with the five minutes before it.
const PIVOT_FOR = 5 * 60;
const BEFORE = 5 * 60;
const S = 5;
const LINE_ORDER = ["GK", "DF", "MF", "AM", "FW"];

/**
 * S1 pitch board (C45): all 22 players and the ball at the match clock, one frame per second.
 * It has no timeline of its own: during a replay it follows the replay bar (Playback), so
 * dragging that bar moves the players too; on a match that is not being replayed it shows
 * where everyone stood at the current clock. Ax36: tap a dot or a name in the line-ups to see
 * who it is; the team-shape layer draws each team's lines with its back line, width and depth,
 * and can set them against the five minutes before the last pivot. Ax41: the line-ups are a card
 * of their own next to the pitch card, so "More details" can put them in their own cell.
 */
export default function PitchBoard() {
  const { match, playback, squads, sheets, teams, events, pivots, playerName, eventById } = useMatch();
  const t = useT();
  // The fixture has no frames to fetch; neither has a page rendered with no browser (the tests).
  const [fixture] = useState(() => typeof window === "undefined" || fixtureMode());
  const now = Math.floor(match.clock);
  const matchId = fixture ? null : match.match_id;
  const { frame, missing } = useFrames(matchId, now);
  const [picked, setPicked] = useState<string | null>(null);
  const [shapeOn, setShapeOn] = useState(true);
  const [compare, setCompare] = useState(false);

  const who = useMemo(() => whoFromSquads(squads), [squads]);
  const lineup = useMemo(() => (sheets ? lineupAt(sheets, events, now) : null), [sheets, events, now]);
  const players = useMemo(() => new Map([...squads.home, ...squads.away].map((p) => [p.player_id, p])), [squads]);
  const roleOf = (id: string): Role | undefined => lineup?.roles.get(id) ?? players.get(id)?.role;
  const tag = (id: string) => {
    const p = players.get(id);
    return [p?.shirt ?? "", p?.name ?? id, roleOf(id) ?? ""].filter((x) => x !== "").join(" · ");
  };

  // The pivot the shape is set against: the latest one at or before the clock, if recent.
  const periods = match.periods?.length ? match.periods : PLAIN_PERIODS;
  const pivot = pivots.find((p) => p.minute * 60 <= now && now - p.minute * 60 <= PIVOT_FOR);
  const minute = Math.floor(now / 60);
  const [from, to] = pivot ? [pivot.minute * 60 - BEFORE, pivot.minute * 60 - 1] : [(minute - 5) * 60, minute * 60 - 1];
  const before = useFrameWindow(compare && shapeOn && minute > 0 ? matchId : null, from, to);
  const beforeLabel = pivot
    ? t("board.beforePivot", { minute: minuteLabel(periods, pivot.minute) })
    : t("board.beforeNow", { from: minuteAt(periods, Math.max(0, from)), to: minuteAt(periods, to + 1) });

  const note = t("board.pitchNote", { team: teams.home.short_name });

  const names = { home: teams.home.short_name, away: teams.away.short_name };
  const roster = (marked: ReadonlySet<string>) => (
    <Card title={t("board.roster")} className="more-roster">
      <Roster squads={squads} frame={frame} now={now} events={events} roleOf={roleOf} picked={picked} marked={marked}
        onPick={setPicked} names={names} />
    </Card>
  );
  if (missing) {
    return (
      <>
        <Card title={t("board.pitch")} note={note} className="more-pitch">
          <div className="empty-box muted">{t("board.pitchNone")}</div>
        </Card>
        {roster(new Set())}
      </>
    );
  }

  // events are newest first: the latest one at or before the frame, and shots just taken.
  const latest = events.find((e) => e.t <= now);
  const shots = events.filter((e) => e.type === "shot" && e.location && e.t <= now && now - e.t <= SHOT_FOR);
  const marked = new Set<string>();
  const mark = (e: MatchEvent | undefined) => {
    if (e?.player_id) marked.add(e.player_id);
    if (e?.receiver_id) marked.add(e.receiver_id);
  };
  if (latest && now - latest.t <= MARK_FOR) mark(latest);
  if (pivot) for (const id of pivot.trigger_event_ids) mark(eventById(id));
  // One frame per second of play: at 1× that is a second between frames, faster replays less.
  const stepMs = Math.max(MIN_STEP_MS, 1000 / (playback?.playing ? match.speed : 1));
  const isHome = (id: string) => who(id).home;
  return (
    <>
      <Card title={t("board.pitch")} note={note} className="pitch-board more-pitch">
        {lineup && (
          <div className="pb-tools">
            <span className="seg" role="group" aria-label={t("board.layers")}>
              <button type="button" aria-pressed={shapeOn} onClick={() => setShapeOn(!shapeOn)}>
                {t("board.layerShape")}
              </button>
              <button type="button" aria-pressed={compare && shapeOn} onClick={() => setCompare(!compare)} disabled={!shapeOn || minute === 0}>
                {t("board.layerCompare")}
              </button>
            </span>
            <small className="muted">{t("board.legend")}</small>
          </div>
        )}
        <div className="pb-main">
          {frame ? (
            <Pitch frame={frame} actions={shots} selected={null} who={who} stepMs={stepMs}
              label={t("detail.pitchLabel", { t: frame.t, n: frame.players.length })}
              picked={picked} onPick={setPicked} marked={marked} tag={tag}
              under={shapeOn && lineup && <ShapeLayer frame={frame} lineup={lineup} before={compare ? before : null} isHome={isHome} />} />
          ) : (
            <div className="empty-box muted">{t("board.pitchLoading")}</div>
          )}
          <p className="pitch-cap">
            {latest && (
              <>
                <b>{latest.clock_label} · {teams[latest.team].short_name}</b> {describe(latest, playerName, t)}
              </>
            )}
            {!playback && <span className="muted">{latest && " · "}{t("board.pitchHint")}</span>}
          </p>
          {shapeOn && lineup && frame && (
            <ShapeTable frame={frame} lineup={lineup} before={compare ? before : undefined} beforeLabel={beforeLabel}
              isHome={isHome} names={names} />
          )}
        </div>
      </Card>
      {roster(marked)}
    </>
  );
}

type IsHome = (id: string) => boolean;

function ShapeLayer({ frame, lineup, before, isHome }: { frame: TrackingFrame; lineup: Lineup; before: TrackingFrame[] | null; isHome: IsHome }) {
  return (
    <g className="shape-layer" pointerEvents="none">
      {(["home", "away"] as const).map((side) => {
        const colour = side === "home" ? "var(--pv-home)" : "var(--pv-away)";
        const now = frameShape(frame, side, lineup.roles, isHome);
        const was = before?.length ? meanShape(before, side, lineup.roles, isHome) : null;
        return (
          <g key={side} className={side}>
            {shapeLines(frame, side, lineup.roles, isHome).map((pts, i) => (
              <polyline key={i} points={pts.map(([x, y]) => `${x * S},${y * S}`).join(" ")} fill="none" stroke={colour}
                strokeWidth={3} strokeOpacity={0.55} strokeLinejoin="round" />
            ))}
            {now && !Number.isNaN(now.backLine) && (
              <line className="back" x1={backLineX(now, side) * S} x2={backLineX(now, side) * S} y1={4} y2={68 * S - 4}
                stroke={colour} strokeWidth={2} strokeDasharray="10 6" />
            )}
            {was && !Number.isNaN(was.backLine) && (
              <line className="was" x1={backLineX(was, side) * S} x2={backLineX(was, side) * S} y1={4} y2={68 * S - 4}
                stroke={colour} strokeWidth={7} strokeOpacity={0.25} />
            )}
          </g>
        );
      })}
    </g>
  );
}

const metres = (v: number | undefined) => (v === undefined || Number.isNaN(v) ? "–" : v.toFixed(0));

function Delta({ now, was }: { now?: number; was?: number }) {
  if (now === undefined || was === undefined || Number.isNaN(now) || Number.isNaN(was)) return null;
  const d = Math.round(now - was);
  return <small className="was"> ← {metres(was)}{d ? ` (${d > 0 ? "+" : ""}${d})` : ""}</small>;
}

const ROWS: [MessageKey, keyof Shape][] = [["board.shapeBack", "backLine"], ["board.shapeWidth", "width"], ["board.shapeDepth", "depth"]];

export function ShapeTable({ frame, lineup, before, beforeLabel, isHome, names }: {
  frame: TrackingFrame; lineup: Lineup; before: TrackingFrame[] | null | undefined; beforeLabel: string;
  isHome: IsHome; names: Record<Side, string>;
}) {
  const t = useT();
  const sides = ["home", "away"] as const;
  const now = (side: Side) => frameShape(frame, side, lineup.roles, isHome);
  const was = (side: Side) => (before?.length ? meanShape(before, side, lineup.roles, isHome) : null);
  const count = (side: Side) => frame.players.filter((p) => isHome(p.player_id) === (side === "home")).length;
  return (
    <div className="shape-table">
      <table>
        <thead>
          <tr><th />{sides.map((s) => <th key={s} className={s}>{names[s]}</th>)}</tr>
        </thead>
        <tbody>
          <tr>
            <th>{t("board.shapeFormation")}</th>
            {sides.map((s) => (
              <td key={s}>{lineup.formation[s]}{count(s) < 11 && count(s) > 0 && <small> · {t("board.players", { n: count(s) })}</small>}</td>
            ))}
          </tr>
          {ROWS.map(([label, k]) => (
            <tr key={k}>
              <th>{t(label)}</th>
              {sides.map((s) => <td key={s}>{metres(now(s)?.[k])}<Delta now={now(s)?.[k]} was={was(s)?.[k]} /></td>)}
            </tr>
          ))}
        </tbody>
      </table>
      <small className="muted">
        {before === undefined ? t("board.shapeNote") : before === null ? t("board.shapeLoading") : t("board.shapeVs", { when: beforeLabel })}
      </small>
    </div>
  );
}

type Status = "on" | "cameOn" | "off" | "sentOff" | "bench";

export function Roster({ squads, frame, now, events, roleOf, picked, marked, onPick, names }: {
  squads: Record<Side, SquadPlayer[]>; frame: TrackingFrame | null; now: number; events: MatchEvent[];
  roleOf: (id: string) => Role | undefined; picked: string | null; marked: ReadonlySet<string>;
  onPick: (id: string | null) => void; names: Record<Side, string>;
}) {
  const t = useT();
  const status = new Map<string, Status>();
  // Oldest first, so a player who came on and went off again ends up off.
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.t > now) continue;
    if (e.substitution) {
      status.set(e.substitution.player_on_id, "cameOn");
      status.set(e.substitution.player_off_id, "off");
    }
    if (isRedCard(e) && e.player_id) status.set(e.player_id, "sentOff");
  }
  const onPitch = new Set(frame?.players.map((p) => p.player_id) ?? []);
  const of = (p: SquadPlayer): Status => {
    const s = status.get(p.player_id);
    if (s === "off" || s === "sentOff") return s;
    return onPitch.has(p.player_id) || (!frame && !s) ? (s ?? "on") : "bench";
  };
  const rank = (p: SquadPlayer) => {
    const s = of(p);
    return (s === "on" || s === "cameOn" ? 0 : 10) + LINE_ORDER.indexOf(lineOf(roleOf(p.player_id)) ?? "FW");
  };
  return (
    <div className="roster" role="group" aria-label={t("board.roster")}>
      {(["home", "away"] as const).map((side) => (
        <div key={side} className={`roster-team ${side}`}>
          <h4>{names[side]}</h4>
          <ol>
            {squads[side].filter((p) => of(p) !== "bench").sort((a, b) => rank(a) - rank(b) || (a.shirt ?? 99) - (b.shirt ?? 99)).map((p) => {
              const s = of(p);
              const gone = s === "off" || s === "sentOff";
              return (
                <li key={p.player_id}>
                  <button type="button" disabled={gone} aria-pressed={picked === p.player_id}
                    className={`${s}${marked.has(p.player_id) ? " marked" : ""}`}
                    onClick={() => onPick(picked === p.player_id ? null : p.player_id)}>
                    <b>{p.shirt ?? ""}</b>
                    <span className="nm">{p.name}</span>
                    <span className="rl">{roleOf(p.player_id) ?? ""}</span>
                    {s !== "on" && <span className={`st ${s}`}>{t(`board.status.${s}` as MessageKey)}</span>}
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      ))}
      <small className="muted roster-hint">{t("board.rosterHint")}</small>
    </div>
  );
}
