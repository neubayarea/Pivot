import { useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import type { ViewerPrefs } from "@pivot/contracts";
import Segmented from "../components/Segmented";
import { Placeholder } from "../components/Skeleton";
import Stamp from "../components/Stamp";
import StateCard from "../components/StateCard";
import {
  byFixture, byMatchday, clubGames, liveNow, pinned, useHub, useNow, type HubFixture, type HubLine, type HubPast, type HubRound, type HubLive, type HubNext, type HubPrediction, type HubTeam,
} from "../data/hub";
import { liveHref } from "../data/liveClock";
import { useLang, usePrefs, useT } from "../i18n";
import "../styles/hub.css";

// The home page (C14, #354): a match centre like FotMob's, Sofascore's or the Premier League
// site's. The simulated live match on top (its clock tied to the wall clock, data/liveClock.ts),
// then every stored match by matchday. A match opens on its own page (`/?match=…`); the six tabs
// there are unchanged. The viewer's team is marked; fan or analyst changes what each line says.

/** The hub is `/` with no match in the link; `?match=` still opens the match page (App.tsx, not in the fixture replay). */
export function isHubPage(pathname: string, search: string): boolean {
  return pathname === "/" && !new URLSearchParams(search).has("match");
}

const LANGUAGES = [
  { value: "en", label: "EN" },
  { value: "zh", label: "中文", lang: "zh" },
  { value: "es", label: "ES" },
] as const;

type Side = "home" | "away";
const kit = (team: HubTeam) => ({ "--kit": team.color }) as CSSProperties;

function HubBar({ prefs, onPrefsChange, teams }: {
  prefs: ViewerPrefs; onPrefsChange: (p: ViewerPrefs) => void; teams: { home: HubTeam; away: HubTeam } | null;
}) {
  const t = useT();
  return (
    <header className="top">
      <Link to="/" className="brand">Pivot</Link>
      <span className="sp" />
      <Segmented
        label={t("top.audience")}
        options={[{ value: "fan", label: t("top.audience.fan") }, { value: "analyst", label: t("top.audience.analyst") }]}
        value={prefs.audience}
        onChange={(audience) => onPrefsChange({ ...prefs, audience })}
      />
      {teams && (
        <Segmented
          label={t("top.team.label")}
          options={[
            { value: "none", label: t("top.team.none") },
            { value: "home", label: teams.home.short_name },
            { value: "away", label: teams.away.short_name },
          ]}
          value={prefs.focus_team ?? "none"}
          onChange={(v) => onPrefsChange({ ...prefs, focus_team: v === "none" ? null : v, focus_player_id: null })}
        />
      )}
      <Segmented
        label={t("top.language")}
        options={LANGUAGES}
        value={prefs.language}
        onChange={(language) => onPrefsChange({ ...prefs, language })}
      />
    </header>
  );
}

function LiveNow({ live, line, fav }: { live: HubLive; line: HubLine; fav: string | null }) {
  const t = useT();
  const now = liveNow(live, useNow());
  const href = liveHref(live.match_id);
  const left = Math.max(1, Math.ceil((live.length_s + 120 - now.clock) / 60));
  return (
    <section className="hub-live" aria-labelledby="hub-live-h">
      <div className="hub-live-head">
        <h2 id="hub-live-h">{t("hub.live.title")}</h2>
        <Stamp tone="live">{t("hub.live.sim")}</Stamp>
        <span className="hub-live-min num" aria-label={t("hub.live.clock", { minute: now.minute })}>
          {now.over ? t("status.finished") : `${now.minute}′`}
        </span>
      </div>
      <Link to={href} className="hub-live-score" aria-label={t("hub.open", {
        home: line.home.name, away: line.away.name, score: `${now.score.home}–${now.score.away}` })}>
        <TeamName team={line.home} fav={fav} />
        <span className="hub-live-goals num">{now.score.home}–{now.score.away}</span>
        <TeamName team={line.away} fav={fav} />
      </Link>
      <div className="hub-live-foot">
        <p>
          {now.over
            ? t("hub.live.break", { n: left })
            : now.lastPivot === null ? t("hub.live.noPivot") : t("hub.live.pivot", { minute: now.lastPivotLabel ?? "" })}
        </p>
        <Link to={href} className="btn pri">{t("hub.live.watch")}</Link>
      </div>
      <p className="hub-note">{t("hub.live.note")}</p>
    </section>
  );
}

function TeamName({ team, fav }: { team: HubTeam; fav: string | null }) {
  const t = useT();
  const mine = fav === team.short_name;
  return (
    <span className={`hub-team${mine ? " mine" : ""}`} style={kit(team)}>
      <span className="hub-dot" aria-hidden="true" />
      {team.name}
      {mine && <span className="sr-only"> ({t("hub.yours")})</span>}
    </span>
  );
}

function verdict(line: HubLine, side: Side): "win" | "draw" | "loss" | null {
  if (line.status !== "finished") return null;
  const us = line.score[side], them = line.score[side === "home" ? "away" : "home"];
  return us > them ? "win" : us < them ? "loss" : "draw";
}

function ResultRow({ line, fav, fan }: { line: HubLine; fav: string | null; fan: boolean }) {
  const t = useT();
  const score = `${line.score.home}–${line.score.away}`;
  const you = fav && (line.home.short_name === fav || line.away.short_name === fav)
    ? verdict(line, line.home.short_name === fav ? "home" : "away") : null;
  return (
    <li>
      <Link to={`/?match=${encodeURIComponent(line.match_id)}&tab=overview`} className="hub-row"
        aria-label={t("hub.open", { home: line.home.name, away: line.away.name, score })}>
        <TeamName team={line.home} fav={fav} />
        <span className="hub-score num">{score}</span>
        <TeamName team={line.away} fav={fav} />
        <span className="hub-meta">{t(fan ? "hub.pivotsFan" : "hub.pivots", { n: line.pivots })}</span>
        <span className="hub-meta">
          {line.best && (fan ? t("hub.bestFan", { name: line.best.name })
            : t("hub.best", { name: line.best.name, rating: line.best.rating.toFixed(1) }))}
        </span>
        <span className="hub-you">{you && t(`hub.you.${you}`)}</span>
      </Link>
    </li>
  );
}

const pct = (x: number) => Math.round(x * 100);

/** Win / draw / win as one bar in the two kits, the share in each part, its 95 % range under it (analysts). */
function PredictionBar({ p, home, away, fan }: { p: HubPrediction; home: HubTeam; away: HubTeam; fan: boolean }) {
  const t = useT();
  const parts = [
    { key: "home_win", share: p.home_win, style: { "--kit": home.color } as CSSProperties },
    { key: "draw", share: p.draw, style: undefined },
    { key: "away_win", share: p.away_win, style: { "--kit": away.color } as CSSProperties },
  ] as const;
  const label = t("hub.pred.label", { home: home.name, away: away.name, h: pct(p.home_win), d: pct(p.draw), a: pct(p.away_win) });
  return (
    <div className="hub-pred">
      <div className="hub-bar" role="img" aria-label={label}>
        {parts.map((x) => (
          <span key={x.key} className={`hub-bar-${x.key}`} style={{ ...x.style, flexGrow: Math.max(x.share, 0.001) }}>
            {x.share >= 0.12 && <span className="num">{pct(x.share)}%</span>}
          </span>
        ))}
      </div>
      {!fan && (
        <div className="hub-ranges num" aria-hidden="true">
          {parts.map((x) => <span key={x.key}>{t("hub.pred.range", { lo: pct(p.ci95[x.key][0]), hi: pct(p.ci95[x.key][1]) })}</span>)}
        </div>
      )}
    </div>
  );
}

function verdictLine(p: HubPrediction, f: HubFixture, t: ReturnType<typeof useT>): string {
  const lead = p.home_win - p.away_win;
  if (Math.abs(lead) < 0.1) return t("hub.pred.close");
  return t("hub.pred.fav", { team: (lead > 0 ? f.home : f.away).name });
}

function FixtureRow({ f, fav, fan }: { f: HubFixture; fav: string | null; fan: boolean }) {
  const t = useT();
  const p = f.prediction;
  const top = p?.scorelines[0];
  const mine = fav !== null && [f.home.short_name, f.away.short_name].includes(fav);
  return (
    <li className={mine ? "mine" : undefined}>
      <Link to={`/?match=${encodeURIComponent(f.match_id)}&tab=preview`} className="hub-fx"
        aria-label={t("hub.next.open", { home: f.home.name, away: f.away.name })}>
        <TeamName team={f.home} fav={fav} />
        {p ? <PredictionBar p={p} home={f.home} away={f.away} fan={fan} /> : <span className="hub-meta">{t("hub.next.noPrediction")}</span>}
        <TeamName team={f.away} fav={fav} />
        <dl className="hub-facts">
          {p && fan && <div><dt>{t("hub.pred.say")}</dt><dd>{verdictLine(p, f, t)}</dd></div>}
          {top && (
            <div>
              <dt>{t(fan ? "hub.pred.scoreFan" : "hub.pred.score")}</dt>
              <dd className="num">{top.home}–{top.away}{!fan && <small> {t("hub.pred.share", { n: pct(top.share) })}</small>}</dd>
            </div>
          )}
          {p && !fan && <div><dt>{t("hub.pred.xg")}</dt><dd className="num">{p.xg.home.toFixed(1)}–{p.xg.away.toFixed(1)}</dd></div>}
        </dl>
      </Link>
    </li>
  );
}

function NextRound({ next, fav, fan }: { next: HubNext; fav: string | null; fan: boolean }) {
  const t = useT();
  const runs = next.fixtures.find((f) => f.prediction)?.prediction?.n_runs ?? 200;
  return (
    <section className="hub-next" aria-labelledby="hub-next-h">
      <div className="hub-section-head">
        <h2 id="hub-next-h">{t("hub.next.title")}</h2>
        <span className="hub-note">{t("hub.next.note", { n: next.matchday, runs })}</span>
      </div>
      <div className="hub-day">
        <ul>{pinned(next.fixtures, fav).map((f) => <FixtureRow key={f.match_id} f={f} fav={fav} fan={fan} />)}</ul>
      </div>
    </section>
  );
}

const LOCALES = { en: "en-GB", zh: "zh-CN", es: "es-ES" } as const;

/** "Wed 28 Oct" / "10月28日周三": the round's day in the fictional calendar. */
function useRoundDate() {
  const lang = useLang();
  return (iso?: string) => iso
    ? new Date(`${iso}T12:00:00Z`).toLocaleDateString(LOCALES[lang], { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" })
    : "";
}

/** One future fixture in the schedule: the two kits, the ground, and the prediction only when one was worked out. */
function ScheduleRow({ f, fav, label }: { f: HubFixture; fav: string | null; label?: string }) {
  const t = useT();
  const p = f.prediction;
  return (
    <li>
      <Link to={`/?match=${encodeURIComponent(f.match_id)}&tab=preview`} className="hub-sched-row"
        aria-label={t("hub.next.open", { home: f.home.name, away: f.away.name })}>
        <span className="hub-meta">{label}</span>
        <TeamName team={f.home} fav={fav} />
        <span className="hub-v" aria-hidden="true">v</span>
        <TeamName team={f.away} fav={fav} />
        <span className="hub-meta">{f.venue}</span>
        {p ? <PredictionBar p={p} home={f.home} away={f.away} fan /> : <span className="hub-meta">{t("hub.sched.later")}</span>}
      </Link>
    </li>
  );
}

/** C15: matchdays 31-38, a round at a time, or the viewer's club's games over all of them. */
function Schedule({ rounds, fav }: { rounds: HubNext[]; fav: string | null }) {
  const t = useT();
  const day = useRoundDate();
  const [picked, setPicked] = useState(String(rounds[0].matchday));
  const [mine, setMine] = useState(false);
  const round = rounds.find((r) => String(r.matchday) === picked) ?? rounds[0];
  const runs = round.fixtures.find((f) => f.prediction)?.prediction?.n_runs;
  const onlyMine = mine && fav !== null;
  return (
    <section className="hub-sched" aria-labelledby="hub-sched-h">
      <div className="hub-section-head">
        <h2 id="hub-sched-h">{t("hub.sched.title")}</h2>
        <span className="hub-note">
          {t("hub.sched.note", { from: rounds[0].matchday, to: rounds[rounds.length - 1].matchday })}
        </span>
      </div>
      <div className="hub-sched-pick">
        {!onlyMine && (
          <Segmented label={t("hub.sched.round")} value={picked} onChange={setPicked}
            options={rounds.map((r) => ({ value: String(r.matchday), label: String(r.matchday) }))} />
        )}
        {fav && (
          <Segmented label={t("hub.sched.show")} value={onlyMine ? "mine" : "all"} onChange={(v) => setMine(v === "mine")}
            options={[{ value: "all", label: t("hub.sched.all") }, { value: "mine", label: t("hub.sched.mine", { team: fav }) }]} />
        )}
      </div>
      <div className="hub-day">
        {onlyMine ? (
          <ul>
            {clubGames(rounds, fav).map(({ round: r, fixture }) => (
              <ScheduleRow key={fixture.match_id} f={fixture} fav={fav}
                label={t("hub.sched.day", { n: r.matchday, date: day(r.date) })} />
            ))}
          </ul>
        ) : (
          <>
            <h3>{t("hub.sched.day", { n: round.matchday, date: day(round.date) })}</h3>
            {runs && <p className="hub-note hub-sched-runs">{t("hub.sched.runs", { n: runs })}</p>}
            <ul>{pinned(round.fixtures, fav).map((f) => <ScheduleRow key={f.match_id} f={f} fav={fav} />)}</ul>
          </>
        )}
      </div>
    </section>
  );
}

/** #364: one game of the season so far; it opens only when its full match is stored. */
function PastRow({ g, fav, label }: { g: HubPast; fav: string | null; label?: string }) {
  const t = useT();
  const score = `${g.score.home}–${g.score.away}`;
  const reds = g.reds.home + g.reds.away;
  const body = (
    <>
      <span className="hub-meta">{label}</span>
      <TeamName team={g.home} fav={fav} />
      <span className="hub-score num">{score}</span>
      <TeamName team={g.away} fav={fav} />
      <span className="hub-meta">{reds > 0 && t("hub.hist.reds", { n: reds })}</span>
      <span className="hub-meta">{g.match_id && t("hub.hist.full")}</span>
    </>
  );
  return (
    <li>
      {g.match_id ? (
        <Link to={`/?match=${encodeURIComponent(g.match_id)}&tab=overview`} className="hub-past-row"
          aria-label={t("hub.open", { home: g.home.name, away: g.away.name, score })}>{body}</Link>
      ) : <div className="hub-past-row">{body}</div>}
    </li>
  );
}

/** #364: the whole league's season so far from the season file, a round at a time, or the viewer's club's games. */
function History({ rounds, fav }: { rounds: HubRound[]; fav: string | null }) {
  const t = useT();
  const day = useRoundDate();
  const [picked, setPicked] = useState(String(rounds[0].matchday));
  const [mine, setMine] = useState(false);
  const round = rounds.find((r) => String(r.matchday) === picked) ?? rounds[0];
  const onlyMine = mine && fav !== null;
  const games = rounds.reduce((n, r) => n + r.results.length, 0);
  return (
    <section className="hub-sched hub-hist" aria-labelledby="hub-hist-h">
      <div className="hub-section-head">
        <h2 id="hub-hist-h">{t("hub.hist.title")}</h2>
        <span className="hub-note">
          {t("hub.hist.note", { n: games, from: rounds[rounds.length - 1].matchday, to: rounds[0].matchday })}
        </span>
      </div>
      <div className="hub-sched-pick">
        {!onlyMine && (
          <label className="hub-hist-pick">
            <span className="hub-meta">{t("hub.sched.round")}</span>
            <select value={picked} onChange={(e) => setPicked(e.target.value)}>
              {rounds.map((r) => <option key={r.matchday} value={String(r.matchday)}>{t("hub.sched.day", { n: r.matchday, date: day(r.date) })}</option>)}
            </select>
          </label>
        )}
        {fav && (
          <Segmented label={t("hub.sched.show")} value={onlyMine ? "mine" : "all"} onChange={(v) => setMine(v === "mine")}
            options={[{ value: "all", label: t("hub.sched.all") }, { value: "mine", label: t("hub.sched.mine", { team: fav }) }]} />
        )}
      </div>
      <div className="hub-day">
        {onlyMine ? (
          <ul>
            {rounds.flatMap((r) => r.results.filter((g) => [g.home.short_name, g.away.short_name].includes(fav))
              .map((g) => <PastRow key={`${r.matchday}-${g.home.short_name}`} g={g} fav={fav}
                label={t("hub.sched.day", { n: r.matchday, date: day(r.date) })} />))}
          </ul>
        ) : (
          <>
            <h3>{t("hub.sched.day", { n: round.matchday, date: day(round.date) })}</h3>
            <ul>{pinned(round.results, fav).map((g) => <PastRow key={g.home.short_name} g={g} fav={fav} />)}</ul>
          </>
        )}
      </div>
    </section>
  );
}

export default function Hub() {
  const { prefs, setPrefs } = usePrefs();
  const t = useT();
  const { data, failed } = useHub();
  const liveLine = data?.matches.find((m) => m.live) ?? null;
  const first = liveLine ?? data?.matches[0] ?? null;
  const teams = first && { home: first.home, away: first.away };
  // The viewer's team is saved as a side of the match they last watched; on the hub it is that club.
  const fav = prefs.focus_team && teams ? teams[prefs.focus_team].short_name : null;
  const results = (data?.matches ?? []).filter((m) => !m.live && m.status === "finished");
  const fan = prefs.audience === "fan";

  return (
    <>
      <HubBar prefs={prefs} onPrefsChange={setPrefs} teams={teams} />
      <main className="page hub">
        <h1>{t("hub.title")}</h1>
        {failed && <StateCard title={t("hub.failed.title")} tone="error">{t("hub.failed")}</StateCard>}
        {!data && !failed && <Placeholder className="hub-ph" label={t("hub.loading")} block={180} lines={6} />}
        {data?.live && liveLine && <LiveNow live={data.live} line={liveLine} fav={fav} />}
        {data?.next && data.next.fixtures.length > 0 && <NextRound next={data.next} fav={fav} fan={fan} />}
        {data?.schedule && data.schedule.length > 0 && <Schedule rounds={data.schedule} fav={fav} />}
        {data && (
          <section className="hub-results" aria-labelledby="hub-results-h">
            <div className="hub-section-head">
              <h2 id="hub-results-h">{t("hub.results.title")}</h2>
              <span className="hub-note">{t("hub.results.note", { n: results.length })}</span>
            </div>
            {data.generating && <p className="hub-note" role="status">{t("hub.generating")}</p>}
            {byMatchday(results).map(([day, lines]) => (
              <div key={day ?? "other"} className="hub-day">
                <h3>{day === null ? t("hub.matchday.none") : t("hub.matchday", { n: day })}</h3>
                <ul>
                  {byFixture(lines).map((group) => group.length === 1
                    ? <ResultRow key={group[0].match_id} line={group[0]} fav={fav} fan={fan} />
                    : (
                      // The same fixture simulated more than once: one game with several runs, said so.
                      <li key={group[0].match_id} className="hub-alt">
                        <p className="hub-note">
                          {t("hub.results.alt", { home: group[0].home.name, away: group[0].away.name, n: group.length })}
                        </p>
                        <ul>{group.map((l) => <ResultRow key={l.match_id} line={l} fav={fav} fan={fan} />)}</ul>
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </section>
        )}
        {data?.history && data.history.length > 0 && <History rounds={data.history} fav={fav} />}
      </main>
    </>
  );
}
