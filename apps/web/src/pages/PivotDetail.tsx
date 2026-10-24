import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Button from "../components/Button";
import Card from "../components/Card";
import { describe } from "../components/EventFeed";
import Pitch from "../components/Pitch";
import { PivotStamp, Severity, pivotHeadline } from "../components/PivotList";
import Scrubber from "../components/Scrubber";
import Sourced, { formatValue } from "../components/Sourced";
import Stamp from "../components/Stamp";
import WhyItTurned from "../components/WhyItTurned";
import { involves, useMatch } from "../data/match";
import { usePrefs } from "../i18n";
import NotFound from "./NotFound";

// Evidence actions stay drawn for a few seconds either side of the event.
const SHOW_FOR = 4;
const PLAY_MS = 250;

// S2 · Pivot detail. Layout follows "06 S2" in docs/design/matchday-programme.html.
export default function PivotDetail() {
  const { id = "" } = useParams();
  const { pivotDetail, eventById, teams, playerName } = useMatch();
  const { prefs, t: tr } = usePrefs();
  const focus = prefs.focus_player_id;
  const detail = pivotDetail(id);
  const pivot = detail?.pivot;
  const sentences = pivot?.narrative?.sentences ?? [];

  const evidence = [...new Set(sentences.flatMap((s) => s.evidence_ids))].flatMap((e) => eventById(e) ?? []);
  const first = evidence.find((e) => e.location) ?? evidence[0];
  const [selected, setSelected] = useState<string | null>(first?.event_id ?? null);
  const [t, setT] = useState(first?.t ?? (pivot ? pivot.minute * 60 : 0));
  const [playing, setPlaying] = useState(false);
  const [disputed, setDisputed] = useState(false);

  // A new pivot id resets the selection and the clock.
  useEffect(() => {
    setSelected(first?.event_id ?? null);
    setT(first?.t ?? (pivot ? pivot.minute * 60 : 0));
    setPlaying(false);
    setDisputed(false);
  }, [id]);

  const [from, to] = detail?.window ?? [0, 0];
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

  const frame = detail.frames[Math.min(detail.frames.length - 1, Math.max(0, t - from))];
  const actions = evidence.filter((e) => e.location && Math.abs(e.t - t) <= SHOW_FOR);
  const picked = selected ? eventById(selected) : undefined;
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
          <Pitch frame={frame} actions={actions} selected={selected} focus={focus}
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
              </>
            ) : (
              <span className="muted">{tr("detail.pickHint")}</span>
            )}
          </p>
        </Card>
        <div className="stack">
          <WhyItTurned pivot={pivot} selected={new Set(selected ? [selected] : [])} onToggle={jump}
            chipHint={tr("detail.chipHint")} />
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
