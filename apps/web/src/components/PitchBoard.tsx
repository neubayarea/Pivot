import { useMemo, useRef, useState } from "react";
import type { MatchEvent, TeamTactics, TrackingFrame } from "@pivot/contracts";
import { fixtureMode, useMatch, type Speed } from "../data/match";
import { frameAt, useFrameStore, useFrameWindow } from "../data/live/frames";
import { cueSpan, cuesAt } from "../data/motion";
import { minuteAt, minuteLabel, PLAIN_PERIODS, useClock } from "../data/clock";
import { isRedCard, type Side, type SquadPlayer } from "../data/view";
import { usePrefs, useT, type MessageKey } from "../i18n";
import Card from "./Card";
import ControlBar, { barKey, type BarMark } from "./ControlBar";
import { describe } from "./EventFeed";
import FollowButton from "./FollowButton";
import { EventCues, smoothFor, usePitchMotion } from "./motion";
import Pitch, { whoFromSquads } from "./Pitch";
import { PlayerNumbers, usePlayerReport } from "./PlayerCard";
import {
  backLineX, frameShape, lineOf, lineupAt, meanShape, shapeLines, tacticsAt, type Lineup, type Role, type Shape,
} from "./shape";
import "../styles/pitch-board.css";

// The board's speeds (Ax61): slow enough to follow a move; 20× is the replay's own default.
const BOARD_SPEEDS = [0.5, 1, 2, 5, 20] as const;
// The back and on buttons and ←/→ move this far; a mark on the line goes this long before it.
const STEP_S = 10;
const LEAD_S = 5;
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
 * Ax67: the shape numbers stay up whichever layer is on, right under the caption, with each
 * team's tactics at the clock below them.
 */
export default function PitchBoard() {
  const { match, playback, squads, sheets, teams, events, pivots, playerName, eventById, preMatch } = useMatch();
  const t = useT();
  const { at, clock, minute: minuteOf } = useClock();
  // The fixture has no frames to fetch; neither has a page rendered with no browser (the tests).
  const [fixture] = useState(() => typeof window === "undefined" || fixtureMode());
  const now = Math.floor(match.clock);
  const matchId = fixture ? null : match.match_id;
  const store = useFrameStore(matchId, match.clock);
  const { missing } = store;
  // The frame React draws from (who is on, rings); the motion loop moves the dots between frames.
  const shown = useRef<TrackingFrame | null>(null);
  const frame = useMemo(() => {
    const f = frameAt(store.around(now), now);
    if (f) shown.current = f;
    return shown.current;
  }, [store.around, store.version, now]);
  const svg = useRef<SVGSVGElement>(null);
  const scrub = useRef<HTMLInputElement>(null);
  const time = useRef<HTMLSpanElement>(null);
  const held = useRef<{ t: number; frames: TrackingFrame[]; smooth: number } | null>(null);
  const clockAt = useRef(match.clock);
  clockAt.current = match.clock;
  usePitchMotion(svg, () => {
    const at = playback?.now ? playback.now() : clockAt.current;
    const frames = store.around(at);
    if (frames.length) held.current = { t: at, frames, smooth: playback?.playing ? smoothFor(match.speed) : 0 };
    return held.current;
  }, (at) => {
    // The thumb follows the clock unless the viewer is holding it.
    if (scrub.current && !scrub.current.matches(":active")) scrub.current.value = String(at);
    const text = clock(at);
    if (time.current && time.current.textContent !== text) time.current.textContent = text;
  });
  const [picked, setPicked] = useState<string | null>(null);
  const [shapeOn, setShapeOn] = useState(true);
  const [compare, setCompare] = useState(false);

  const who = useMemo(() => whoFromSquads(squads), [squads]);
  const lineup = useMemo(() => (sheets ? lineupAt(sheets, events, now) : null), [sheets, events, now]);
  const plans = preMatch?.plans;
  const tactics = useMemo(() => (plans ? tacticsAt({ home: plans.home.tactics, away: plans.away.tactics }, events, now) : null),
    [plans, events, now]);
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
  // Ax59: a player picked in the list or on the pitch takes over the card until Back.
  const roster = (marked: ReadonlySet<string>) => (
    <Card title={t("board.roster")} className="more-roster">
      {picked && players.has(picked) ? (
        <PlayerDetail player={players.get(picked)!} role={roleOf(picked)} onBack={() => setPicked(null)} />
      ) : (
        <Roster squads={squads} frame={frame} now={now} events={events} roleOf={roleOf} picked={picked} marked={marked}
          onPick={setPicked} names={names} />
      )}
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

  // events are newest first: the latest one at or before the frame, and the cues of the last few seconds.
  const speed = playback?.playing ? match.speed : 1;
  const cues = cuesAt(events, now, cueSpan(speed));
  const cued = cues.length ? eventById(cues.at(-1)!.id) : undefined;
  const latest = cued ?? events.find((e) => e.t <= now);
  const marked = new Set<string>();
  const mark = (e: MatchEvent | undefined) => {
    if (e?.player_id) marked.add(e.player_id);
    if (e?.receiver_id) marked.add(e.receiver_id);
  };
  if (latest && now - latest.t <= MARK_FOR) mark(latest);
  if (pivot) for (const id of pivot.trigger_event_ids) mark(eventById(id));
  const isHome = (id: string) => who(id).home;
  const marks: BarMark[] = [
    ...events.filter((e) => e.type === "shot" && e.shot_outcome === "goal").map((e): BarMark => ({
      t: e.t, kind: "goal", side: e.team, label: t("ctl.goal", { minute: at(e.t), team: teams[e.team].short_name }),
    })),
    ...[...new Set(pivots.map((p) => p.minute))].map((m): BarMark => ({ t: m * 60, kind: "pivot", label: t("ctl.pivot", { minute: minuteOf(m) }) })),
  ];
  const play = (on: boolean) => {
    if (!playback) return;
    if (on && match.clock >= playback.end) playback.seek(0);    // play again from kick-off
    playback.setPlaying(on);
  };
  const seekBy = (d: number) => playback && playback.seek((playback.now?.() ?? match.clock) + d);
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
        <div className="pb-main" tabIndex={playback ? 0 : undefined} aria-keyshortcuts={playback ? "Space K ArrowLeft ArrowRight" : undefined}
          onKeyDown={playback ? (e) => barKey(e, { toggle: () => play(!playback.playing), seekBy, step: STEP_S }) : undefined}>
          {frame ? (
            <Pitch frame={frame} actions={[]} selected={null} who={who} animated svgRef={svg}
              className={playback && !playback.playing ? "paused" : undefined}
              label={t("detail.pitchLabel", { t: frame.t, n: frame.players.length })}
              picked={picked} onPick={setPicked} marked={marked} tag={tag}
              under={shapeOn && lineup && <ShapeLayer frame={frame} lineup={lineup} before={compare ? before : null} isHome={isHome} />}
              over={<EventCues cues={cues} />} />
          ) : (
            <div className="empty-box muted">{t("board.pitchLoading")}</div>
          )}
          {playback && (
            <ControlBar playing={playback.playing} onPlaying={play} value={match.clock} min={0} max={playback.end} onSeek={playback.seek}
              step={STEP_S} speeds={BOARD_SPEEDS} speed={match.speed} onSpeed={(s) => playback.setSpeed(s as Speed)} marks={marks}
              lead={LEAD_S} format={clock} inputRef={scrub} timeRef={time} />
          )}
          {playback && <small className="muted clip-keys">{t("board.keys")}</small>}
          <div className="pb-side">
            <p className="pitch-cap" aria-live="off">
              {latest && (
                <span className={`cap-ev ${latest.team}`}>
                  <b>{at(latest.t)}′</b> {describe(latest, playerName, t)}
                </span>
              )}
              {!playback && <span className="muted">{latest && " · "}{t("board.pitchHint")}</span>}
            </p>
            {((lineup && frame) || tactics) && (
              <ShapeTable frame={frame} lineup={lineup} before={compare && shapeOn ? before : undefined} beforeLabel={beforeLabel}
                isHome={isHome} names={names} tactics={tactics} />
            )}
          </div>
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
  const t = useT();
  if (now === undefined || was === undefined || Number.isNaN(now) || Number.isNaN(was)) return null;
  const d = Math.round(now) - Math.round(was);
  return <small className="was" title={t("board.shapeWas", { v: metres(was) })}> ({d > 0 ? "+" : d < 0 ? "−" : "±"}{Math.abs(d)})</small>;
}

const ROWS: [MessageKey, keyof Shape][] = [["board.shapeBack", "backLine"], ["board.shapeWidth", "width"], ["board.shapeDepth", "depth"]];
// The plan's settings the board lists (Ax67), worded as on the Pre-match tab; a switch only when a side has it on.
const TACTICS = ["press", "line_height", "tempo", "passing", "attack_focus"] as const satisfies readonly (keyof TeamTactics)[];
const SWITCHES = ["counter_attack", "offside_trap"] as const satisfies readonly (keyof TeamTactics)[];

export function ShapeTable({ frame, lineup, before, beforeLabel, isHome, names, tactics }: {
  frame: TrackingFrame | null; lineup: Lineup | null; before: TrackingFrame[] | null | undefined; beforeLabel: string;
  isHome: IsHome; names: Record<Side, string>; tactics?: Record<Side, TeamTactics> | null;
}) {
  const { prefs, t } = usePrefs();
  const sides = ["home", "away"] as const;
  const shape = frame && lineup ? { frame, lineup } : null;
  const now = (side: Side) => shape && frameShape(shape.frame, side, shape.lineup.roles, isHome);
  const was = (side: Side) => (shape && before?.length ? meanShape(before, side, shape.lineup.roles, isHome) : null);
  const count = (side: Side) => frame?.players.filter((p) => isHome(p.player_id) === (side === "home")).length ?? 0;
  const label = (key: string) => t((prefs.audience === "fan" ? `plan.fan.${key}` : `plan.${key}`) as MessageKey);
  const switches = tactics ? SWITCHES.filter((k) => tactics.home[k] || tactics.away[k]) : [];
  return (
    <div className="shape-table">
      <table>
        <thead>
          <tr><th />{sides.map((s) => <th key={s} className={s}>{names[s]}</th>)}</tr>
        </thead>
        {shape && (
          <tbody>
            <tr>
              <th>{t("board.shapeFormation")}</th>
              {sides.map((s) => (
                <td key={s}>{shape.lineup.formation[s]}{count(s) < 11 && count(s) > 0 && <small> ({t("board.players", { n: count(s) })})</small>}</td>
              ))}
            </tr>
            {ROWS.map(([name, k]) => (
              <tr key={k}>
                <th>{t(name)}</th>
                {sides.map((s) => <td key={s}>{metres(now(s)?.[k])}<Delta now={now(s)?.[k]} was={was(s)?.[k]} /></td>)}
              </tr>
            ))}
          </tbody>
        )}
        {tactics && (
          <tbody className="tactics">
            <tr className="sec"><th colSpan={3}>{t("board.tactics")}</th></tr>
            {TACTICS.map((k) => (
              <tr key={k}>
                <th>{label(k)}</th>
                {sides.map((s) => <td key={s}>{t(`plan.${k}.${tactics[s][k]}` as MessageKey)}</td>)}
              </tr>
            ))}
            {switches.map((k) => (
              <tr key={k}>
                <th>{t(`plan.flag.${k}`)}</th>
                {sides.map((s) => <td key={s}>{tactics[s][k] ? t("board.tacticOn") : "–"}</td>)}
              </tr>
            ))}
          </tbody>
        )}
      </table>
      {shape && (
        <small className="muted">
          {before === undefined ? t("board.shapeNote") : before === null ? t("board.shapeLoading") : t("board.shapeVs", { when: beforeLabel })}
        </small>
      )}
    </div>
  );
}

/** One player in the line-ups card: who, where, and their numbers up to the clock (PlayerCard's). */
export function PlayerDetail({ player, role, onBack }: { player: SquadPlayer; role: Role | undefined; onBack: () => void }) {
  const { match, teams, playback, squads } = useMatch();
  const t = useT();
  const { at } = useClock();
  const side: Side = squads.home.some((p) => p.player_id === player.player_id) ? "home" : "away";
  // Whole minutes, so a running clock refetches once a minute; the whole match once it is over.
  const upTo = match.status === "finished" && !playback ? null : Math.floor(match.clock / 60) * 60;
  const report = usePlayerReport(match.match_id, player.player_id, upTo);
  return (
    <div className={`roster-detail ${side}`}>
      <button type="button" className="btn ghost pd-back" onClick={onBack} autoFocus>← {t("board.rosterBack")}</button>
      <div className="pd-hd">
        <b className="pd-no num">{player.shirt ?? ""}</b>
        <span>
          <span className="pd-nm">{player.name}</span>
          <small className="muted">{[teams[side].name, role ?? player.role].filter(Boolean).join(" · ")} · 0′–{at(upTo ?? match.clock)}′</small>
        </span>
        <FollowButton playerId={player.player_id} name={player.name} />
      </div>
      {report === null ? <p className="muted">{t("board.rosterNoStats")}</p> : <PlayerNumbers report={report} />}
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
