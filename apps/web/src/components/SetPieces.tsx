// Set pieces and shot clips on the match board (Ax37), folded below the moments like "More details".
// Set pieces: every corner, every free kick near the goal it attacks and every penalty, with what
// came of it; opening one replays it in the clip player (Ax56), from the players lining up to the
// shot or clearance, with who stood in the box, how the defenders marked and the wall until the kick.
// Shots: one card per shot; opening one replays the attack on the pitch in the clip player shared
// with the key moments (Ax42). The rules are in data/setpieces.ts.
import { useMemo, useState } from "react";
import type { TrackingFrame } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { fromShot, setPieceClip } from "../data/clips";
import { useFrameWindow } from "../data/live/frames";
import { useMatch } from "../data/match";
import {
  frameBefore, goalX, MARK_M, setPieces, setupAt, shotClips, tally, PITCH_W,
  type SetPiece, type SetPieceResult, type ShotClip, type ShotSource,
} from "../data/setpieces";
import { useT, type MessageKey } from "../i18n";
import { describe } from "./EventFeed";
import ClipPlayer, { useFramesMatch, usePeople } from "./ClipPlayer";
import Segmented from "./Segmented";
import "../styles/setpieces.css";

const S = 5;
/** Off until the simulator lines players up for set pieces (#245): its marking and walls are not real yet. */
const SHOW_MARKING = false;
const HASHES = ["#set-pieces", "#shots"] as const;
type Tab = "set" | "shots";

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
  if (sp.kind === "corner") return t("sp.corner");
  return sp.kind === "penalty" ? t("sp.penalty") : t(`sp.fk.${sp.zone ?? "deep"}` as MessageKey);
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
            {t(sums[side].penalties ? "sp.sumPens" : "sp.sum", {
              corners: sums[side].corners, fks: sums[side].freeKicks, pens: sums[side].penalties, shots: sums[side].shots, goals: sums[side].goals,
            })}
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

/** The set piece replayed in the shared clip player; the box, marking and wall are drawn until the kick. */
function SetPieceView({ sp }: { sp: SetPiece }) {
  const { events, teams, playerName } = useMatch();
  const t = useT();
  const { at, clock } = useClock();
  const people = usePeople();
  const matchId = useFramesMatch();
  const clip = useMemo(() => setPieceClip(sp, events), [sp, events]);
  const frames = useFrameWindow(matchId, sp.event.t - 2, sp.event.t);
  const still = frames ? frameBefore(frames, sp.event.t) : null;
  const setup = still ? setupAt(still, sp, people.isHome, people.isKeeper) : null;
  const att = teams[sp.event.team].short_name;
  const def = teams[sp.event.team === "home" ? "away" : "home"].short_name;
  const names = (ids: string[]) => ids.map((id) => people.tag(id)).join(", ");
  const marks = SHOW_MARKING && sp.kind !== "penalty";
  const [from, to] = clip.parts[0];

  return (
    <ClipPlayer clip={clip} label={t("sp.clipLabel", { minute: `${at(sp.event.t)}′`, kind: kindLabel(sp, t) })} intro={t("sp.clipIntro")}
      title={<>{at(sp.event.t)}′ · {kindLabel(sp, t)} · {att} · {playerName(sp.event.player_id)} <Result r={sp.result} /></>}
      under={(frame, tm) => {
        const before = tm < sp.event.t;
        return <SetupLayer frame={frame} sp={sp} pairs={marks && before && setup ? setup.pairs : []} wall={marks && before && setup ? setup.wall : []} />;
      }}>
      {!SHOW_MARKING && sp.kind !== "penalty" && <small className="sp-sim">{t("sp.simNote")}</small>}
      {setup && (
        <dl className="sp-facts">
          <dt>{t("sp.inBox")}</dt>
          <dd>{t("sp.inBoxVal", { att, n: setup.attackersInBox.length, def, m: setup.defendersInBox.length })}</dd>
          {marks && (
            <>
              <dt>{t("sp.marking")}</dt>
              <dd>
                {setup.marking ? <b>{t(`sp.marking.${setup.marking}` as MessageKey)}</b> : t("sp.marking.few")}
                {setup.marking && <small> · {t("sp.markingWhy", { k: setup.pairs.length, n: setup.attackersInBox.length, m: MARK_M })}</small>}
              </dd>
            </>
          )}
          {marks && sp.kind === "free_kick" && (
            <>
              <dt>{t("sp.wall")}</dt>
              <dd>{setup.wall.length ? t("sp.wallVal", { n: setup.wall.length, who: names(setup.wall) }) : t("sp.wallNone")}</dd>
            </>
          )}
          <dt>{t("sp.then")}</dt>
          <dd>{sp.decidedBy ? `${at(sp.decidedBy.t)}′ ${teams[sp.decidedBy.team].short_name} · ${describe(sp.decidedBy, playerName, t)}` : t("sp.result.kept")}</dd>
        </dl>
      )}
      <small className="muted">{t(marks ? "sp.how" : "sp.howPlain", { from: clock(from), to: clock(to) })}</small>
    </ClipPlayer>
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
        {open && <ShotClipView key={open.shot.event_id} clip={open} />}
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

/** The attack before one shot, in the shared clip player. */
function ShotClipView({ clip }: { clip: ShotClip }) {
  const { teams, playerName } = useMatch();
  const t = useT();
  const { at, clock } = useClock();
  const people = usePeople();
  const c = useMemo(() => fromShot(clip), [clip]);
  return (
    <ClipPlayer clip={c} label={t("shots.pitchLabel", { minute: `${at(clip.shot.t)}′` })} intro={t("shots.buildUp")}
      title={<>
        {at(clip.shot.t)}′ · {playerName(clip.shot.player_id)} · {teams[clip.shot.team].short_name}
        {" "}<span className="sh-out">{t(`shots.out.${clip.shot.shot_outcome ?? "off_target"}` as MessageKey)}</span>
      </>}>
      <p className="clip-chain">
        <b>{t("shots.involved")}</b> {c.involved.map((id) => people.tag(id)).join(" → ")}
      </p>
      <small className="muted">{t("shots.how", { from: clock(clip.from), to: clock(clip.to) })}</small>
    </ClipPlayer>
  );
}
