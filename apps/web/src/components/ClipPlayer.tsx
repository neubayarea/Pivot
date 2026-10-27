// One player for every clip on the pitch (Ax42): a shot's attack (Ax37), a key moment (Ax38) and a
// set piece (Ax56).
// It runs on clip time with requestAnimationFrame, moved by the real time since the last screen
// frame times the speed, so the dots glide between the once-a-second frames at any speed.
// Keys, with the clip focused: Space or K plays and pauses, ←/→ go back and on a second (Shift: 5),
// Home goes to the start, R plays it again, − and + change the speed.
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import type { TrackingFrame } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { advance, clipLength, nextRate, partAt, RATES, toMatch, type Clip, type ClipMark, type Rate } from "../data/clips";
import type { KeyKind } from "../data/keyMoments";
import { useFrameWindow } from "../data/live/frames";
import { fixtureMode, useMatch, type Side } from "../data/match";
import { clipBall, frameBetween } from "../data/setpieces";
import { useT, type MessageKey } from "../i18n";
import { describe } from "./EventFeed";
import Pitch, { whoFromSquads } from "./Pitch";
import Segmented from "./Segmented";
import { lineupAt } from "./shape";
import "../styles/setpieces.css";

const S = 5;

/** Who is who for these pitches: side, shirt, keeper, and the tooltip text. */
export function usePeople() {
  const { squads, sheets, events } = useMatch();
  const who = useMemo(() => whoFromSquads(squads), [squads]);
  const players = useMemo(() => new Map([...squads.home, ...squads.away].map((p) => [p.player_id, p])), [squads]);
  const roles = useMemo(() => (sheets ? lineupAt(sheets, events, Infinity).roles : null), [sheets, events]);
  return {
    who,
    isHome: (id: string) => who(id).home,
    isKeeper: (id: string) => (roles?.get(id) ?? players.get(id)?.role) === "GK",
    tag: (id: string) => {
      const p = players.get(id);
      return [p?.shirt ?? "", p?.name ?? id].filter((x) => x !== "").join(" · ");
    },
  };
}

/** The match id frames are fetched for; null in the fixture or with no browser (the tests). */
export function useFramesMatch(): string | null {
  const { match } = useMatch();
  const [fixture] = useState(() => typeof window === "undefined" || fixtureMode());
  return fixture ? null : match.match_id;
}

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

// The speed picked last carries over to the next clip opened.
let lastRate: Rate = 1;
const reducedMotion = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export default function ClipPlayer({ clip, label, title, intro, under, children }: {
  clip: Clip;
  /** The pitch's accessible name. */
  label: string;
  title?: ReactNode;
  /** The caption before the first event is reached. */
  intro: string;
  /** Drawn on the pitch under the players, for the frame shown at match second `tm`. */
  under?: (frame: TrackingFrame, tm: number) => ReactNode;
  /** Under the caption: who was involved, how the clip was cut. */
  children?: ReactNode;
}) {
  const { teams, playerName } = useMatch();
  const t = useT();
  const { at, clock } = useClock();
  const people = usePeople();
  const matchId = useFramesMatch();
  const { parts } = clip;
  const length = clipLength(parts);
  const frames = useFrameWindow(matchId, parts[0][0], parts.at(-1)![1]);
  const ready = !!frames?.length;
  const [pos, setPosState] = useState(0);
  const posAt = useRef(0);
  const setPos = (c: number) => {
    posAt.current = Math.min(length, Math.max(0, c));
    setPosState(posAt.current);
  };
  const [playing, setPlaying] = useState(() => !reducedMotion());
  const [rate, setRateState] = useState<Rate>(lastRate);
  const rateAt = useRef(rate);
  const setRate = (r: Rate) => {
    lastRate = rateAt.current = r;
    setRateState(r);
  };
  const [pickedPlayer, setPickedPlayer] = useState<string | null>(clip.named);

  useEffect(() => {
    if (!playing || !ready) return;
    let id = 0;
    let last: number | null = null;
    const step = (now: number) => {
      const next = advance(posAt.current, last === null ? 0 : now - last, rateAt.current, length);
      last = now;
      posAt.current = next;
      setPosState(next);
      if (next >= length) setPlaying(false);
      else id = requestAnimationFrame(step);
    };
    id = requestAnimationFrame(step);
    return () => cancelAnimationFrame(id);
  }, [playing, ready, length]);

  const tm = toMatch(parts, pos);
  const part = parts[partAt(parts, pos)];
  const between = frames ? frameBetween(frames, tm) : null;
  const flying = frames && clip.shot ? clipBall(clip.shot, frames, tm) : null;
  const frame = between && flying ? { ...between, ball: { ...between.ball, ...flying, owner_id: null } } : between;
  const reached = clip.marks.filter((m) => m.t <= tm);
  const banner = reached.at(-1);
  const now = clip.events.filter((e) => e.t <= tm).at(-1);
  const drawn = clip.events.filter((e) => (e.type === "pass" || e.type === "shot") && e.t >= part[0] && e.t <= tm);
  const ended = pos >= length;
  const replay = () => {
    setPos(0);
    setPlaying(true);
  };
  const toggle = () => (!playing && ended ? replay() : setPlaying(!playing));

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const tag = (e.target as HTMLElement).tagName;
    const by = e.shiftKey ? 5 : 1;
    if ((e.key === " " || e.key === "k" || e.key === "K") && tag !== "BUTTON") toggle();
    else if (e.key === "ArrowLeft") setPos(posAt.current - by);
    else if (e.key === "ArrowRight") setPos(posAt.current + by);
    else if (e.key === "Home") setPos(0);
    else if (e.key === "End") setPos(length);
    else if (e.key === "r" || e.key === "R") replay();
    else if (e.key === "-" || e.key === "_") setRate(nextRate(rateAt.current, -1));
    else if (e.key === "+" || e.key === "=") setRate(nextRate(rateAt.current, 1));
    else return;
    e.preventDefault();
  };

  let pitch: ReactNode;
  if (matchId === null || (frames && !frames.length)) pitch = <div className="empty-box muted">{t("board.pitchNone")}</div>;
  else if (!frame || !frames) pitch = <div className="empty-box muted">{t("board.pitchLoading")}</div>;
  else {
    const trailTo = clip.shot && clip.shot.t >= part[0] ? Math.min(tm, clip.shot.t - 1) : tm;
    pitch = (
      <Pitch frame={frame} actions={drawn} selected={null} who={people.who} stepMs={1} label={label}
        picked={pickedPlayer} onPick={setPickedPlayer} tag={people.tag} marked={new Set(clip.involved)}
        under={<>{under?.(frame, tm)}<BallTrail frames={frames.filter((f) => f.t >= part[0])} pos={trailTo} now={frame} /></>}
        over={<Marks marks={reached} tm={tm} />} />
    );
  }

  return (
    <div className={`clip${banner?.kind === "goal" ? " goal" : ""}`} role="group" aria-label={label} tabIndex={0} onKeyDown={onKey}
      aria-keyshortcuts="Space K ArrowLeft ArrowRight Home End R - +">
      {(title || banner) && (
        <h4>
          {title}
          {banner && <span className={`clip-banner ${banner.kind}`}>{t(`clip.banner.${banner.kind}` as MessageKey)}</span>}
        </h4>
      )}
      {pitch}
      <div className="clip-ctl">
        <button type="button" className="play" aria-label={t(playing ? "scrub.pause" : "scrub.play")} onClick={toggle} disabled={!ready}>
          {playing ? "❚❚" : "▶"}
        </button>
        <button type="button" className="again" aria-label={t("clip.replay")} title={t("clip.replay")} onClick={replay} disabled={!ready}>↺</button>
        <input type="range" min={0} max={length} step={0.05} value={pos} aria-label={t("scrub.time")}
          aria-valuetext={clock(tm)} disabled={!ready}
          onChange={(e) => {
            setPlaying(false);
            setPos(Number(e.target.value));
          }} />
        <span className="num">{clock(tm)}</span>
        <Segmented label={t("shots.speed")} value={String(rate)} onChange={(v) => setRate(Number(v) as Rate)}
          options={RATES.map((r) => ({ value: String(r), label: `${r}×` }))} />
      </div>
      <p className="pitch-cap">
        {now ? <><b>{at(now.t)}′ · {teams[now.team].short_name}</b> {describe(now, playerName, t)}</> : <span className="muted">{intro}</span>}
      </p>
      {children}
      <small className="muted clip-keys">{t("clip.keys")}</small>
    </div>
  );
}

/** Each key moment reached so far, marked where it happened; the newest with a ring for a second. */
function Marks({ marks, tm }: { marks: ClipMark[]; tm: number }) {
  return (
    <g className="clip-marks" pointerEvents="none">
      {marks.map((m, i) => m.at && (
        <g key={i}>
          {tm - m.t < 1 && <circle cx={m.at[0] * S} cy={m.at[1] * S} r={14 + (tm - m.t) * 10} fill="none" stroke="var(--pv-gold)" strokeWidth={3} opacity={1 - (tm - m.t)} />}
          <KeyMark kind={m.kind} side={m.side} x={m.at[0] * S} y={m.at[1] * S - 20} size={1.6} />
        </g>
      ))}
    </g>
  );
}

/** Where the ball has been since this part of the clip began, up to now (frames up to `pos`, then the ball as drawn). */
function BallTrail({ frames, pos, now }: { frames: TrackingFrame[]; pos: number; now: TrackingFrame }) {
  const pts = [...frames.filter((f) => f.t <= pos).map((f) => f.ball), now.ball];
  return (
    <polyline className="ball-trail" pointerEvents="none" fill="none"
      points={pts.map((b) => `${b.x * S + 8},${b.y * S - 8}`).join(" ")} />
  );
}
