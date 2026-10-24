// Broadcast overlay (FR-26, the rules' Render step): a transparent 1920×1080 page for an OBS
// browser source. Score bug top right, one pivot card bottom left, timed on the match clock.
// `?clock=mm:ss` holds one moment, `?speed=N` replays the timeline locally, `?preview=1` puts a
// placeholder pitch behind it. See docs/design/matchday-programme.html, section 09.
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import type { OverlayCard, OverlayScoreboard } from "@pivot/contracts";
import { api } from "../data/live/api";
import { cardAt, clockMode, replayClock, severityDots, type ClockMode } from "../overlay/clock";
import "../styles/overlay.css";

const STAGE_W = 1920;
const STAGE_H = 1080;
/** Same as the slide-out animation in overlay.css. */
const EXIT_MS = 450;
const POLL_MS = 1000;

type OverlayState = { clock: number | null; scoreboard: OverlayScoreboard | null; card: OverlayCard | null; error: string | null };

function useOverlay(matchId: string, mode: ClockMode): OverlayState {
  const [state, setState] = useState<OverlayState>({ clock: null, scoreboard: null, card: null, error: null });
  const modeKey = JSON.stringify(mode);

  useEffect(() => {
    let stopped = false;
    const timers: ReturnType<typeof setInterval>[] = [];
    const fail = (e: unknown) => !stopped && setState((s) => ({ ...s, error: String((e as Error).message ?? e) }));
    const frame = (clock?: number, keepCard = false) =>
      api.getOverlay(matchId, clock).then((f) => {
        if (stopped) return;
        setState((s) => ({ ...s, scoreboard: f.scoreboard, error: null, ...(keepCard ? {} : { clock: f.clock, card: f.card }) }));
      }, fail);

    if (mode.kind === "fixed") {
      void frame(mode.at);
    } else if (mode.kind === "live") {
      void frame();
      timers.push(setInterval(() => void frame(), POLL_MS));
    } else {
      // Cards come from the timeline on a local clock, so they land on the exact second at any
      // speed; the score bug is fetched once a second for wherever the replay has got to.
      const start = performance.now();
      const now = () => replayClock(mode, performance.now() - start);
      api.getOverlayTimeline(matchId).then((tl) => {
        if (stopped) return;
        const tick = () => {
          const clock = now();
          setState((s) => (s.clock === clock ? s : { ...s, clock, card: cardAt(tl.cards, clock) }));
        };
        tick();
        timers.push(setInterval(tick, 50));
      }, fail);
      void frame(now(), true);
      timers.push(setInterval(() => void frame(now(), true), POLL_MS));
    }
    return () => {
      stopped = true;
      timers.forEach(clearInterval);
    };
    // modeKey stands in for mode, which is a fresh object on every render.
  }, [matchId, modeKey]);

  return state;
}

/** Keeps the previous card mounted while it slides out, then brings in the next one. */
function usePresence(card: OverlayCard | null): { shown: OverlayCard | null; leaving: boolean } {
  const [shown, setShown] = useState(card);
  const [leaving, setLeaving] = useState(false);
  const latest = useRef(card);
  latest.current = card;
  const id = card?.pivot_id ?? null;

  useEffect(() => {
    if (id === (shown?.pivot_id ?? null)) {
      setLeaving(false);
      return;
    }
    if (shown === null) {
      setShown(latest.current);
      return;
    }
    setLeaving(true);
    const t = setTimeout(() => {
      setShown(latest.current);
      setLeaving(false);
    }, EXIT_MS);
    return () => clearTimeout(t);
    // Only a change of card starts a transition; `shown` is read, not watched.
  }, [id]);

  return { shown, leaving };
}

/** Scale the 1920×1080 stage to fit the window, so a preview tab looks like the OBS output. */
function useStageScale(): number {
  const fit = () => Math.min(window.innerWidth / STAGE_W, window.innerHeight / STAGE_H);
  const [scale, setScale] = useState(fit);
  useEffect(() => {
    const onResize = () => setScale(fit());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return scale;
}

function ScoreBug({ sb }: { sb: OverlayScoreboard }) {
  const { home, away, home_penalties: hp, away_penalties: ap } = sb.score;
  const pens = hp !== null && ap !== null ? ` (${hp}–${ap})` : "";
  return (
    <div className="ovbug num" aria-label="Score">
      <span>
        {sb.home_short} {home}–{away}
        {pens} {sb.away_short}
      </span>
      <b>{sb.clock_label}</b>
    </div>
  );
}

function Card({ card, leaving }: { card: OverlayCard; leaving: boolean }) {
  return (
    <div className={`ov${leaving ? " leaving" : ""}`}>
      <span className="mn num">{card.minute_label}</span>
      <div className="bd">
        <span className="k">Pivot · Momentum → {card.direction_team}</span>
        <span className="x">{card.headline}</span>
        {card.subline && <span className="s">{card.subline}</span>}
      </div>
      <div className="ft">
        <span>{card.status === "confirmed" ? "Pivot · verified by event data" : "Pivot · partial data"}</span>
        <b aria-label={`Severity ${card.severity} of 3`}>{severityDots(card.severity)}</b>
      </div>
    </div>
  );
}

function fmtClock(t: number): string {
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}

export default function Overlay() {
  const { matchId = "" } = useParams();
  const [params] = useSearchParams();
  const mode = useMemo(() => clockMode(params), [params]);
  const preview = params.get("preview") === "1";
  const { clock, scoreboard, card, error } = useOverlay(matchId, mode);
  const { shown, leaving } = usePresence(card);
  const scale = useStageScale();

  // The page is a layer over video: no paper, no dots, nothing behind the graphics.
  useEffect(() => {
    document.documentElement.classList.add("overlay-page");
    return () => document.documentElement.classList.remove("overlay-page");
  }, []);

  const modeLabel = mode.kind === "replay" ? `replay ×${mode.speed}` : mode.kind;
  return (
    <div className={`ovs${preview ? " preview" : ""}`} style={{ transform: `translate(-50%, -50%) scale(${scale})` }}>
      {preview && (
        <span className="tag num">
          Broadcast feed (placeholder) · {modeLabel}
          {clock !== null && ` · ${fmtClock(clock)}`}
          {error && ` · ${error}`}
        </span>
      )}
      {scoreboard && <ScoreBug sb={scoreboard} />}
      <div aria-live="polite">{shown && <Card key={shown.pivot_id} card={shown} leaving={leaving} />}</div>
    </div>
  );
}
