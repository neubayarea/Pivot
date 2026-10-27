// The pitch on every screen frame (Ax61). React draws the board once a second or so (who is on,
// rings, cues); one requestAnimationFrame loop moves the dots, the ball and its trail by setting
// their transforms directly, from the frames around the clock (data/motion), so nothing is
// re-rendered to make them move and they glide at any speed. A seek shows the new spot at once.
import { useEffect, useRef, type RefObject } from "react";
import type { TrackingFrame } from "@pivot/contracts";
import { ballTrail, poseAt, smoothPose, trimJumps, type Cue } from "../data/motion";

const S = 5;
const W = 105 * S;
const H = 68 * S;
// The ball is drawn up and to the right of its spot, so it is not hidden under its carrier's dot.
export const BALL_OFF = [8, -8] as const;

/**
 * The clock and the frames around it; `ball` overrides where the frames have the ball (a clip's shot
 * in flight); `smooth` averages the players over that many seconds either side, so a fast replay
 * shows where play is going rather than every one-second jolt in the data.
 */
export type MotionSource = () => { t: number; frames: readonly TrackingFrame[]; ball?: readonly [number, number] | null; smooth?: number } | null;

/** The smoothing for a replay speed: none up to 5×, then up to a second either side. */
export const smoothFor = (speed: number) => (speed <= 5 ? 0 : Math.min(1, speed / 20));

/** Moves the `[data-player]`, `[data-ball]` and `[data-trail]` elements of `svg` on every screen frame; `onFrame` gets the clock. */
export function usePitchMotion(svg: RefObject<SVGSVGElement | null>, read: MotionSource, onFrame?: (t: number) => void) {
  const readRef = useRef(read);
  readRef.current = read;
  const frameRef = useRef(onFrame);
  frameRef.current = onFrame;
  useEffect(() => {
    if (typeof requestAnimationFrame === "undefined") return;
    let id = 0;
    let lastT = NaN;
    let lastFrames: readonly TrackingFrame[] | null = null;
    let lastCount = -1;
    const step = () => {
      id = requestAnimationFrame(step);
      const el = svg.current;
      const got = readRef.current();
      if (!el || !got) return;
      frameRef.current?.(got.t);
      const dots = el.querySelectorAll<SVGGElement>("[data-player]");
      // React never sets these transforms, so a dot without one has just been drawn (a sub, a pick).
      let fresh = dots.length !== lastCount;
      for (const d of dots) if (!d.hasAttribute("transform")) fresh = true;
      // Nothing moved and nothing new: leave the page alone.
      if (!fresh && got.t === lastT && got.frames === lastFrames) return;
      const pose = got.smooth ? smoothPose(got.frames, got.t, got.smooth) : poseAt(got.frames, got.t);
      if (!pose) return;
      if (got.ball) pose.ball = got.ball;
      lastT = got.t;
      lastFrames = got.frames;
      lastCount = dots.length;
      for (const d of dots) {
        const p = pose.players.get(d.dataset.player!);
        if (!p) continue;
        // Only the dots that moved, so a still player costs no style work.
        const tr = `translate(${(p[0] * S).toFixed(2)} ${(p[1] * S).toFixed(2)})`;
        if (d.getAttribute("transform") !== tr) d.setAttribute("transform", tr);
      }
      const ball = el.querySelector("[data-ball]");
      ball?.setAttribute("transform", `translate(${(pose.ball[0] * S + BALL_OFF[0]).toFixed(2)} ${(pose.ball[1] * S + BALL_OFF[1]).toFixed(2)})`);
      const trail = el.querySelector("[data-trail]");
      if (trail) {
        const pts = trimJumps([...ballTrail(got.frames, got.t), pose.ball]);
        trail.setAttribute("points", pts.map(([x, y]) => `${(x * S + BALL_OFF[0]).toFixed(2)},${(y * S + BALL_OFF[1]).toFixed(2)}`).join(" "));
      }
    };
    id = requestAnimationFrame(step);
    return () => cancelAnimationFrame(id);
  }, [svg]);
}

const colour = (team: Cue["team"]) => (team === "home" ? "var(--pv-home)" : "var(--pv-away)");

/**
 * What just happened, drawn where it happened and faded out (Ax61): a pass as a line from passer to
 * receiver, a shot as a line to goal with a mark where it ended (a ring for a goal, a cross
 * otherwise), a tackle or interception as a flash, a foul as "!", a card as the card. In the
 * acting team's colour. The fade runs on real time, so it reads the same at any replay speed.
 */
export function EventCues({ cues }: { cues: Cue[] }) {
  return (
    <g className="cues" pointerEvents="none">
      {cues.map((c) => {
        const [x1, y1] = [c.from[0] * S, c.from[1] * S];
        // A shot ends on the goal line: its mark is kept just inside the pitch so it is not cut in half.
        const [x2, y2] = c.to ? [Math.min(W - 9, Math.max(9, c.to[0] * S)), Math.min(H - 9, Math.max(9, c.to[1] * S))] : [x1, y1];
        const stroke = colour(c.team);
        return (
          <g key={c.id} className={`cue ${c.kind}`} data-cue={c.kind}>
            {(c.kind === "pass" || c.kind === "shot" || c.kind === "goal") && c.to && (
              <>
                {/* A pale edge under the line keeps it apart from the team-shape lines in the same colour. */}
                <line className="cue-line" x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--pv-sheet)" strokeOpacity={0.85} pathLength={1}
                  strokeWidth={c.kind === "pass" ? 6 : 8} strokeLinecap="round" />
                <line className="cue-line" x1={x1} y1={y1} x2={x2} y2={y2} stroke={stroke} pathLength={1}
                  strokeWidth={c.kind === "pass" ? 3 : 4.5} strokeLinecap="round" />
              </>
            )}
            {c.kind === "pass" && c.to && <circle cx={x2} cy={y2} r={5} fill={stroke} stroke="var(--pv-sheet)" strokeWidth={1.5} />}
            {c.kind === "goal" && c.to && (
              <>
                <circle className="cue-flash" cx={x2} cy={y2} r={18} fill="none" stroke={stroke} strokeWidth={4} />
                <circle cx={x2} cy={y2} r={8} fill={stroke} stroke="var(--pv-sheet)" strokeWidth={3} />
              </>
            )}
            {c.kind === "shot" && c.to && (
              <path d={`M${x2 - 7},${y2 - 7} L${x2 + 7},${y2 + 7} M${x2 + 7},${y2 - 7} L${x2 - 7},${y2 + 7}`} stroke={stroke} strokeWidth={4} strokeLinecap="round" />
            )}
            {c.kind === "tackle" && (
              <>
                <circle className="cue-flash" cx={x1} cy={y1} r={16} fill="none" stroke={stroke} strokeWidth={3} />
                <circle cx={x1} cy={y1} r={4} fill={stroke} />
              </>
            )}
            {c.kind === "foul" && (
              <g transform={`translate(${x1} ${y1 - 22})`}>
                <circle r={9} fill="var(--pv-sheet)" stroke={stroke} strokeWidth={2.5} />
                <text y={4.5} fontSize={13} fontWeight={800} textAnchor="middle" fill={stroke}>!</text>
              </g>
            )}
            {(c.kind === "yellow" || c.kind === "red") && (
              <rect x={x1 - 6} y={y1 - 32} width={12} height={17} rx={1.5} fill={c.kind === "red" ? "var(--pv-red)" : "var(--pv-card-yellow)"}
                stroke="var(--pv-ink)" strokeWidth={1.5} transform={`rotate(12 ${x1} ${y1 - 24})`} />
            )}
          </g>
        );
      })}
    </g>
  );
}
