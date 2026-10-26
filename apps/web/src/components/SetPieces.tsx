// Set pieces and shot clips on the match board (Ax37), folded below the moments like "More details".
// Set pieces: every corner and every free kick near the goal it attacks, with what came of it, and
// the pitch stopped at the kick showing who stood in the box, how the defenders marked and the wall.
// Shots: one card per shot; opening one replays the attack on the pitch, the dots moved smoothly
// between the once-a-second frames. The rules are in data/setpieces.ts.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { TrackingFrame } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { useFrameWindow } from "../data/live/frames";
import { fixtureMode, useMatch } from "../data/match";
import {
  clipBall, frameBefore, frameBetween, goalX, MARK_M, setPieces, setupAt, shotClips, tally, PITCH_W,
  type SetPiece, type SetPieceResult, type ShotClip, type ShotSource,
} from "../data/setpieces";
import { useT, type MessageKey } from "../i18n";
import { describe } from "./EventFeed";
import Pitch, { whoFromSquads } from "./Pitch";
import Segmented from "./Segmented";
import { lineupAt } from "./shape";
import "../styles/setpieces.css";

const S = 5;
const HASHES = ["#set-pieces", "#shots"] as const;
type Tab = "set" | "shots";

/** Who is who for these pitches: side, shirt, keeper, and the tooltip text. */
function usePeople() {
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
function useFramesMatch(): string | null {
  const { match } = useMatch();
  const [fixture] = useState(() => typeof window === "undefined" || fixtureMode());
  return fixture ? null : match.match_id;
}

export default function SetPiecesAndShots() {
  const { events } = useMatch();
  const t = useT();
  const [open, setOpen] = useState(() => typeof window !== "undefined" && (HASHES as readonly string[]).includes(window.location.hash));
  const [tab, setTab] = useState<Tab>(() => (typeof window !== "undefined" && window.location.hash === "#shots" ? "shots" : "set"));
  const corners = events.filter((e) => e.type === "pass" && e.pass_type === "corner").length;
  const shots = events.filter((e) => e.type === "shot").length;
  return (
    <details className="more set-shots" id="set-pieces" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>
        {t("sp.title")} <small>{t("sp.titleNote", { corners, shots })}</small>
      </summary>
      {open && (
        <div className="more-bd">
          <Segmented label={t("sp.title")} value={tab} onChange={setTab}
            options={[{ value: "set", label: t("sp.tabSet") }, { value: "shots", label: t("sp.tabShots") }]} />
          {tab === "set" ? <SetPieceBoard /> : <ShotBoard />}
        </div>
      )}
    </details>
  );
}

// --- Set pieces -------------------------------------------------------------------------------

const RESULT_TONE: Record<SetPieceResult, string> = { goal: "goal", shot: "shot", cleared: "", lost: "", kept: "" };

function Result({ r }: { r: SetPieceResult }) {
  const t = useT();
  return <span className={`sp-res ${RESULT_TONE[r]}`}>{t(`sp.result.${r}` as MessageKey)}</span>;
}

function kindLabel(sp: SetPiece, t: ReturnType<typeof useT>) {
  return sp.kind === "corner" ? t("sp.corner") : t(`sp.fk.${sp.zone ?? "deep"}` as MessageKey);
}

export function SetPieceBoard() {
  const { events, teams, playerName } = useMatch();
  const t = useT();
  const { at } = useClock();
  const [all, setAll] = useState(false);
  const list = useMemo(() => setPieces(events), [events]);
  const shown = list.filter((s) => all || s.kind === "corner" || s.zone !== "deep");
  const sums = tally(shown);
  const [picked, setPicked] = useState<string | null>(null);
  const open = shown.find((s) => s.event.event_id === picked) ?? shown[0] ?? null;
  if (!list.length) return <p className="muted">{t("sp.none")}</p>;
  return (
    <div className="sp">
      <div className="sp-sum">
        {(["home", "away"] as const).map((side) => (
          <p key={side} className={side}>
            <b>{teams[side].short_name}</b>{" "}
            {t("sp.sum", { corners: sums[side].corners, fks: sums[side].freeKicks, shots: sums[side].shots, goals: sums[side].goals })}
          </p>
        ))}
        <label className="sp-all">
          <input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> {t("sp.showDeep", { n: list.length - list.filter((s) => s.kind === "corner" || s.zone !== "deep").length })}
        </label>
      </div>
      <div className="sp-split">
        <ol className="sp-list" aria-label={t("sp.tabSet")}>
          {shown.map((s) => (
            <li key={s.event.event_id}>
              <button type="button" aria-pressed={s === open} className={s.event.team} onClick={() => setPicked(s.event.event_id)}>
                <b className="num">{at(s.event.t)}′</b>
                <span className="tm">{teams[s.event.team].short_name}</span>
                <span className="kd">{kindLabel(s, t)}</span>
                <span className="nm">{playerName(s.event.player_id)}</span>
                <Result r={s.result} />
              </button>
            </li>
          ))}
        </ol>
        {open && <SetPieceView key={open.event.event_id} sp={open} />}
      </div>
    </div>
  );
}

function SetPieceView({ sp }: { sp: SetPiece }) {
  const { teams, playerName } = useMatch();
  const t = useT();
  const { at } = useClock();
  const people = usePeople();
  const matchId = useFramesMatch();
  const frames = useFrameWindow(matchId, sp.event.t - 2, sp.event.t);
  const frame = frames ? frameBefore(frames, sp.event.t) : null;
  const setup = frame ? setupAt(frame, sp, people.isHome, people.isKeeper) : null;
  const [pickedPlayer, setPickedPlayer] = useState<string | null>(null);
  const att = teams[sp.event.team].short_name;
  const def = teams[sp.event.team === "home" ? "away" : "home"].short_name;
  const names = (ids: string[]) => ids.map((id) => people.tag(id)).join(", ");

  let pitch: ReactNode;
  if (matchId === null || (frames && !frames.length)) pitch = <div className="empty-box muted">{t("board.pitchNone")}</div>;
  else if (!frame || !setup) pitch = <div className="empty-box muted">{t("board.pitchLoading")}</div>;
  else {
    pitch = (
      <Pitch frame={frame} actions={[sp.event]} selected={null} who={people.who} stepMs={1}
        label={t("sp.pitchLabel", { minute: `${at(sp.event.t)}′` })}
        picked={pickedPlayer} onPick={setPickedPlayer} tag={people.tag}
        marked={new Set(setup.pairs.flat())}
        under={<SetupLayer frame={frame} sp={sp} pairs={setup.pairs} wall={setup.wall} />} />
    );
  }

  return (
    <div className="sp-view">
      <h4>
        {at(sp.event.t)}′ · {kindLabel(sp, t)} · {att} · {playerName(sp.event.player_id)} <Result r={sp.result} />
      </h4>
      {pitch}
      {setup && (
        <dl className="sp-facts">
          <dt>{t("sp.inBox")}</dt>
          <dd>{t("sp.inBoxVal", { att, n: setup.attackersInBox.length, def, m: setup.defendersInBox.length })}</dd>
          <dt>{t("sp.marking")}</dt>
          <dd>
            {setup.marking ? <b>{t(`sp.marking.${setup.marking}` as MessageKey)}</b> : t("sp.marking.few")}
            {setup.marking && <small> · {t("sp.markingWhy", { k: setup.pairs.length, n: setup.attackersInBox.length, m: MARK_M })}</small>}
          </dd>
          {sp.kind === "free_kick" && (
            <>
              <dt>{t("sp.wall")}</dt>
              <dd>{setup.wall.length ? t("sp.wallVal", { n: setup.wall.length, who: names(setup.wall) }) : t("sp.wallNone")}</dd>
            </>
          )}
          <dt>{t("sp.then")}</dt>
          <dd>{sp.decidedBy ? `${at(sp.decidedBy.t)}′ ${teams[sp.decidedBy.team].short_name} · ${describe(sp.decidedBy, playerName, t)}` : t("sp.result.kept")}</dd>
        </dl>
      )}
      <small className="muted">{t("sp.how")}</small>
    </div>
  );
}

/** The attacked box, each attacker joined to his marker, and the wall as one thick bar. */
function SetupLayer({ frame, sp, pairs, wall }: { frame: TrackingFrame; sp: SetPiece; pairs: [string, string][]; wall: string[] }) {
  const where = new Map(frame.players.map((p) => [p.player_id, p]));
  const gx = goalX(sp.event.team);
  const bx = gx === 0 ? 0 : gx - 16.5;
  const wallPts = wall.map((id) => where.get(id)).filter((p) => p !== undefined);
  return (
    <g className="sp-layer" pointerEvents="none">
      <rect x={bx * S} y={(PITCH_W / 2 - 20.15) * S} width={16.5 * S} height={40.3 * S} className="sp-box" />
      {pairs.map(([a, d]) => {
        const p = where.get(a);
        const q = where.get(d);
        return p && q ? <line key={a} x1={p.x * S} y1={p.y * S} x2={q.x * S} y2={q.y * S} className="sp-pair" /> : null;
      })}
      {wallPts.length >= 2 && (
        <polyline points={wallPts.map((p) => `${p.x * S},${p.y * S}`).join(" ")} className="sp-wall" />
      )}
    </g>
  );
}

// --- Shots ------------------------------------------------------------------------------------

type SourceFilter = "all" | ShotSource;

export function ShotBoard() {
  const { events } = useMatch();
  const t = useT();
  const clips = useMemo(() => shotClips(events), [events]);
  const [source, setSource] = useState<SourceFilter>("all");
  const shown = clips.filter((c) => source === "all" || c.source === source);
  const [picked, setPicked] = useState<string | null>(null);
  const open = shown.find((c) => c.shot.event_id === picked) ?? shown.find((c) => c.shot.shot_outcome === "goal") ?? shown[0] ?? null;
  if (!clips.length) return <p className="muted">{t("shots.none")}</p>;
  const count = (s: ShotSource) => clips.filter((c) => c.source === s).length;
  return (
    <div className="sh">
      <Segmented label={t("shots.filter")} value={source} onChange={setSource} options={[
        { value: "all", label: t("shots.all", { n: clips.length }) },
        { value: "set_piece", label: t("shots.src.set_piece.n", { n: count("set_piece") }) },
        { value: "open_play", label: t("shots.src.open_play.n", { n: count("open_play") }) },
        { value: "counter", label: t("shots.src.counter.n", { n: count("counter") }) },
      ]} />
      <div className="sp-split sh-split">
        <div className="sh-cards">
          {shown.map((c) => <ShotCard key={c.shot.event_id} c={c} on={c === open} onPick={() => setPicked(c.shot.event_id)} />)}
          {!shown.length && <p className="muted">{t("shots.noneHere")}</p>}
        </div>
        {open && <ClipPlayer key={open.shot.event_id} clip={open} />}
      </div>
    </div>
  );
}

function ShotCard({ c, on, onPick }: { c: ShotClip; on: boolean; onPick: () => void }) {
  const { teams, playerName } = useMatch();
  const t = useT();
  const { at } = useClock();
  const goal = c.shot.shot_outcome === "goal";
  return (
    <button type="button" className={`sh-card ${c.shot.team}${goal ? " goal" : ""}`} aria-pressed={on} onClick={onPick}>
      <span className="sh-min num">{at(c.shot.t)}′</span>
      <span className="sh-who"><b>{playerName(c.shot.player_id)}</b> · {teams[c.shot.team].short_name}</span>
      <span className="sh-out">{t(`shots.out.${c.shot.shot_outcome ?? "off_target"}` as MessageKey)}</span>
      <span className="sh-meta">
        <span className="num">{t("shots.xg", { xg: (c.shot.xg ?? 0).toFixed(2) })}</span>
        <span>{t(`shots.src.${c.source}` as MessageKey)}</span>
      </span>
    </button>
  );
}

const RATES = [0.5, 1] as const;

/** The attack before one shot, played on the pitch with the dots moved smoothly between frames. */
function ClipPlayer({ clip }: { clip: ShotClip }) {
  const { teams, playerName } = useMatch();
  const t = useT();
  const { at, clock } = useClock();
  const people = usePeople();
  const matchId = useFramesMatch();
  const frames = useFrameWindow(matchId, clip.from, clip.to);
  const [pos, setPosState] = useState(clip.from);
  const posAt = useRef(clip.from);
  const setPos = (p: number) => {
    posAt.current = p;
    setPosState(p);
  };
  const [playing, setPlaying] = useState(true);
  const [rate, setRate] = useState<(typeof RATES)[number]>(1);
  const [pickedPlayer, setPickedPlayer] = useState<string | null>(null);
  const last = useRef<number | null>(null);
  const ready = !!frames?.length;

  useEffect(() => {
    if (!playing || !ready) return;
    let id = 0;
    last.current = null;
    const step = (now: number) => {
      const dt = last.current === null ? 0 : (now - last.current) / 1000;
      last.current = now;
      const next = Math.min(clip.to, posAt.current + dt * rate);
      posAt.current = next;
      setPosState(next);
      if (next >= clip.to) setPlaying(false);
      else id = requestAnimationFrame(step);
    };
    id = requestAnimationFrame(step);
    return () => cancelAnimationFrame(id);
  }, [playing, ready, rate, clip.to]);

  const between = frames ? frameBetween(frames, pos) : null;
  const flying = frames ? clipBall(clip, frames, pos) : null;
  const frame = between && flying ? { ...between, ball: { ...between.ball, ...flying, owner_id: null } } : between;
  const goal = clip.shot.shot_outcome === "goal";
  const shotTaken = pos >= clip.shot.t;
  const played = clip.chain.filter((e) => e.t <= pos);
  const now = played.at(-1);
  const order = [...new Set(clip.chain.map((e) => e.player_id).filter((id): id is string => !!id))];
  const toggle = () => {
    if (!playing && pos >= clip.to) setPos(clip.from);
    setPlaying(!playing);
  };

  let pitch: ReactNode;
  if (matchId === null || (frames && !frames.length)) pitch = <div className="empty-box muted">{t("board.pitchNone")}</div>;
  else if (!frame || !frames) pitch = <div className="empty-box muted">{t("board.pitchLoading")}</div>;
  else {
    pitch = (
      <Pitch frame={frame} actions={played.filter((e) => e.type === "pass" || e.type === "shot")} selected={null} who={people.who}
        stepMs={1} label={t("shots.pitchLabel", { minute: `${at(clip.shot.t)}′` })}
        picked={pickedPlayer} onPick={setPickedPlayer} tag={people.tag} marked={new Set(order)}
        under={<BallTrail frames={frames} pos={Math.min(pos, clip.shot.t - 1)} now={frame} />} />
    );
  }

  return (
    <div className={`clip${goal ? " goal" : ""}`}>
      <h4>
        {at(clip.shot.t)}′ · {playerName(clip.shot.player_id)} · {teams[clip.shot.team].short_name}
        {" "}<span className="sh-out">{t(`shots.out.${clip.shot.shot_outcome ?? "off_target"}` as MessageKey)}</span>
        {goal && shotTaken && <span className="clip-goal">{t("shots.goalBanner")}</span>}
      </h4>
      {pitch}
      <div className="clip-ctl">
        <button type="button" className="play" aria-label={t(playing ? "scrub.pause" : "scrub.play")} onClick={toggle} disabled={!ready}>
          {playing ? "❚❚" : "▶"}
        </button>
        <input type="range" min={clip.from} max={clip.to} step={0.1} value={pos} aria-label={t("scrub.time")}
          aria-valuetext={clock(pos)} disabled={!ready}
          onChange={(e) => {
            setPlaying(false);
            setPos(Number(e.target.value));
          }} />
        <span className="num">{clock(pos)}</span>
        <Segmented label={t("shots.speed")} value={String(rate)} onChange={(v) => setRate(Number(v) as (typeof RATES)[number])}
          options={RATES.map((r) => ({ value: String(r), label: `${r}×` }))} />
      </div>
      <p className="pitch-cap">
        {now ? <><b>{at(now.t)}′ · {teams[now.team].short_name}</b> {describe(now, playerName, t)}</> : <span className="muted">{t("shots.buildUp")}</span>}
      </p>
      <p className="clip-chain">
        <b>{t("shots.involved")}</b> {order.map((id) => people.tag(id)).join(" → ")}
      </p>
      <small className="muted">{t("shots.how", { from: clock(clip.from), to: clock(clip.to) })}</small>
    </div>
  );
}

/** Where the ball has been since the clip began, up to now (frames up to `pos`, then the ball as drawn). */
function BallTrail({ frames, pos, now }: { frames: TrackingFrame[]; pos: number; now: TrackingFrame }) {
  const pts = [...frames.filter((f) => f.t <= pos).map((f) => f.ball), now.ball];
  return (
    <polyline className="ball-trail" pointerEvents="none" fill="none"
      points={pts.map((b) => `${b.x * S + 8},${b.y * S - 8}`).join(" ")} />
  );
}
