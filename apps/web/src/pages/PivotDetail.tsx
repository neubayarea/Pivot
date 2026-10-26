import { useEffect, useMemo, useState } from "react";
import type { TrackingFrame } from "@pivot/contracts";
import { Link, useParams } from "react-router-dom";
import Button from "../components/Button";
import Card from "../components/Card";
import { describe } from "../components/EventFeed";
import Pitch, { whoFromSquads } from "../components/Pitch";
import { PivotStamp, Severity, pivotHeadline } from "../components/PivotList";
import Scrubber from "../components/Scrubber";
import Sourced, { formatValue } from "../components/Sourced";
import Stamp from "../components/Stamp";
import WhyItTurned from "../components/WhyItTurned";
import { type Frames, useFrames } from "../data/live/frames";
import { fixtureMode, involves, useMatch } from "../data/match";
import { inWindow } from "../data/window";
import { usePrefs } from "../i18n";
import NotFound from "./NotFound";

// Evidence actions stay drawn for a few seconds either side of the event.
const SHOW_FOR = 4;
const PLAY_MS = 250;

/**
 * The frame S2 draws at second `t`, and what the caption should say about it. The fixture brings
 * its own frames; on live data the detail has one empty frame and the players come from the
 * API's tracking frames (the same fetch as the pitch board), or stay off when it has none.
 */
export function detailFrame(own: TrackingFrame[], from: number, t: number, fetched: Frames):
  { frame: TrackingFrame; note: "loading" | "none" | null } {
  const mine = own[Math.min(own.length - 1, Math.max(0, t - from))];
  if (mine.players.length) return { frame: mine, note: null };
  if (fetched.frame) return { frame: fetched.frame, note: null };
  return { frame: { ...mine, t }, note: fetched.missing ? "none" : "loading" };
}

// S2 · Pivot detail. Layout follows "06 S2" in docs/design/matchday-programme.html.
export default function PivotDetail() {
  const { id = "" } = useParams();
  const { match, squads, pivotDetail, eventById, teams, playerName } = useMatch();
  const { prefs, t: tr } = usePrefs();
  const focus = prefs.focus_player_id;
  const detail = pivotDetail(id);
  const pivot = detail?.pivot;
  const sentences = pivot?.narrative?.sentences ?? [];

  const evidence = [...new Set(sentences.flatMap((s) => s.evidence_ids))].flatMap((e) => eventById(e) ?? []);
  const first = evidence.find((e) => e.location) ?? evidence[0];
  const [from, to] = detail?.window ?? [0, 0];
  // The clock starts on the first evidence, or the window's edge when that falls outside it.
  const start = Math.min(to, Math.max(from, first?.t ?? (pivot ? pivot.minute * 60 : 0)));
  const [selected, setSelected] = useState<string | null>(first?.event_id ?? null);
  const [t, setT] = useState(start);
  const [playing, setPlaying] = useState(false);
  const [disputed, setDisputed] = useState(false);
  // The fixture's details carry their own frames; a page rendered with no browser (the tests) fetches none.
  const [fixture] = useState(() => typeof window === "undefined" || fixtureMode());
  const fetched = useFrames(fixture ? null : match.match_id, t);
  const who = useMemo(() => (fixture ? undefined : whoFromSquads(squads)), [fixture, squads]);

  // A new pivot id resets the selection and the clock.
  useEffect(() => {
    setSelected(first?.event_id ?? null);
    setT(start);
    setPlaying(false);
    setDisputed(false);
  }, [id]);

  useEffect(() => {
    if (!playing) return;
    const h = setInterval(() => setT((s) => (s >= to ? from : s + 1)), PLAY_MS);
    return () => clearInterval(h);
  }, [playing, from, to]);

  if (!detail || !pivot) {
    return (
      <NotFound title={tr("detail.notFound.title")}>
        <p>{tr("detail.notFound.body", { id })}</p>
      </NotFound>
    );
  }

  const { frame, note } = detailFrame(detail.frames, from, t, fetched);
  const actions = evidence.filter((e) => e.location && Math.abs(e.t - t) <= SHOW_FOR);
  const picked = selected ? eventById(selected) : undefined;
  // Evidence the timeline cannot reach gets no tick; its chip and the caption say so instead.
  const outside = new Set(evidence.filter((e) => !inWindow(detail.window, e.t)).map((e) => e.event_id));
  const claims = sentences.reduce((n, s) => n + s.claims.length, 0);
  const [beforeWin, afterWin] = [detail.beforeAfter[0]?.before.stat_ref.window, detail.beforeAfter[0]?.after.stat_ref.window];

  const jump = (eventId: string) => {
    const e = eventById(eventId);
    setSelected(eventId);
    setPlaying(false);
    if (e) setT(Math.min(to, Math.max(from, e.t)));
  };

  return (
    <>
      {pivot.status === "degraded" && (
        <div className="banner warn" role="status">
          {tr("detail.degraded")}
        </div>
      )}
      <div className="back">
        <Link to="/">{tr("detail.back")}</Link>
      </div>
      <div className="s2-head">
        <span className="min">{pivot.minute}′</span>
        <h2>{pivotHeadline(pivot, teams, tr)}</h2>
        <span className="acts">
          <Link to={`/whatif/${pivot.pivot_id}`} className="btn pri">
            {tr("detail.whatIf")}
          </Link>
          <Button variant="ghost" aria-pressed={disputed} onClick={() => setDisputed(!disputed)}>
            {tr(disputed ? "detail.flagged" : "detail.dispute")}
          </Button>
        </span>
        <span className="meta">
          <Severity level={pivot.severity} />
          {pivot.status === "confirmed" ? (
            <Stamp tone="ok">{tr("detail.verified", { claims, evidence: evidence.length })}</Stamp>
          ) : (
            <PivotStamp status={pivot.status} />
          )}
          {disputed && <Stamp tone="warn">{tr("detail.flaggedStamp")}</Stamp>}
          <span className="pipe">{tr("pivot.momentumTo", { team: teams[pivot.direction].name })}</span>
        </span>
      </div>
      <div className="grid2">
        <Card title={tr("detail.pitch")} note={
          <>
            {tr("detail.pitchNote", { from: from / 60, to: to / 60, team: teams.home.short_name })}
            {focus && <> · <span className="focus-key">{tr("detail.focusNote", { player: playerName(focus) })}</span></>}
          </>
        }>
          <Pitch frame={frame} actions={actions} selected={selected} focus={focus} who={who}
            label={picked
              ? tr("detail.pitchLabelPicked", { t: frame.t, n: frame.players.length, seq: picked.seq })
              : tr("detail.pitchLabel", { t: frame.t, n: frame.players.length })} />
          <Scrubber window={detail.window} t={t} onChange={(s) => { setT(s); setPlaying(false); }}
            playing={playing} onPlayingChange={setPlaying} pivotMinutes={[pivot.minute]}
            marks={evidence.map((e) => ({ t: e.t, on: e.event_id === selected, mine: involves(e, focus) }))} />
          <p className="pitch-cap">
            {picked ? (
              <>
                <b>#{picked.seq} · {picked.clock_label}</b> {describe(picked, playerName, tr)}
                {!picked.location && <span className="muted">{tr("detail.noDraw")}</span>}
                {outside.has(picked.event_id) && <span className="muted">{tr("detail.outside")}</span>}
              </>
            ) : (
              <span className="muted">{tr("detail.pickHint")}</span>
            )}
            {note && <span className="muted"> · {tr(note === "none" ? "board.pitchNone" : "board.pitchLoading")}</span>}
          </p>
        </Card>
        <div className="stack">
          <WhyItTurned pivot={pivot} selected={new Set(selected ? [selected] : [])} onToggle={jump}
            chipHint={tr("detail.chipHint")} outside={outside} />
          {detail.beforeAfter.length > 0 && beforeWin && afterWin && (
            <Card title={tr("detail.ba")} note={tr("detail.baNote")}>
              <table className="ba">
                <thead>
                  <tr>
                    <th>{tr("detail.baMetric")}</th>
                    <th>{beforeWin[0]}–{beforeWin[1]}′</th>
                    <th>{afterWin[0]}–{afterWin[1]}′</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.beforeAfter.map((r) => (
                    <tr key={r.label}>
                      <td>{r.label}</td>
                      {[r.before, r.after].map((c, i) => (
                        <td key={i} className="big">
                          <Sourced claim={c}>{formatValue(c)}</Sourced>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
