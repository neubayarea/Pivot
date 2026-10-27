// The pre-match tab (Ax60): what the API sends about the match before kick-off and the page used to
// drop (#276): the occasion, form and table, head-to-head, the news, what could tip the players, and
// the ties between the two squads. A subject the match has no data for is left out, never shown as
// zeros. Headlines and effect notes are written by the simulator in English.
// C11 (Ax63): a match preview's order. `PreMatchTop` is the tale of the tape (table, form,
// head-to-head) under one strip of match facts; `PreMatchStories` is the news and the context
// effects, then the ties. Each person and team carries a small swatch in its own kit colour.
import type { ContextEffect, MatchContext, PastMeeting, TeamForm } from "@pivot/contracts";
import { useMatch, type Side, type TeamPlan } from "../data/match";
import { usePrefs, type MessageKey, type T } from "../i18n";
import Card from "./Card";
import LangTag from "./LangTag";
import "../styles/prematch.css";

const SIDES: Side[] = ["home", "away"];
/** Effects that are about people meeting again; they go in the ties card, not the factors card. */
const TIE_SOURCES = new Set<ContextEffect["source"]>(["former_club", "former_teammate", "former_coach"]);
/** Per-player effects every match has (a rating average, a big-match rating); too many and too small to list. */
const ROUTINE_SOURCES = new Set<ContextEffect["source"]>(["form", "competition"]);
const MAX_FACTORS = 5;
const MAX_TIES = 6;

/** "2nd", "11th": English only; the other tables write the place without a suffix. */
const ordinal = (n: number) => (n % 100 >= 11 && n % 100 <= 13 ? "th" : (["th", "st", "nd", "rd"][n % 10] ?? "th"));

/** A small square in the team's kit colour, before a team or person's name. */
export const Kit = ({ side }: { side: Side | undefined }) => (side ? <i className={`pre-kit ${side}`} aria-hidden="true" /> : null);

function usePre() {
  const { preMatch, teams, squads, playerName } = useMatch();
  const { prefs, t } = usePrefs();
  if (!preMatch) return null;
  const { plans } = preMatch;
  const fan = prefs.audience === "fan";
  // Fan mode titles the same cards in plain words, as the stats do.
  const title = (key: string) => t((fan ? `pre.fan.${key}` : `pre.${key}`) as MessageKey);
  const coaches = new Map(SIDES.map((s) => [plans[s].coach.coach_id, plans[s].coach.name]));
  const teamOf = new Map<string, Side>(SIDES.flatMap((s) => [
    [s, s] as const, [plans[s].coach.coach_id, s] as const, ...squads[s].map((p) => [p.player_id, s] as const),
  ]));
  const name = (id: string) => (id === "home" || id === "away" ? teams[id].name : (coaches.get(id) ?? playerName(id)));
  return { ...preMatch, teams, t, fan, title, name, teamOf: (id: string) => teamOf.get(id) };
}

/** The occasion, then both sides' place, points and form facing each other, and the head-to-head. */
export function PreMatchTop() {
  const pre = usePre();
  if (!pre) return null;
  const { context, plans, teams, t, title } = pre;
  return (
    <section className="card pre-top" aria-label={title("occasion")}>
      <Occasion context={context} t={t} />
      <div className="pre-tape">
        <Form form={context.form} t={t} title={title("form")} name={(s) => teams[s].name} />
        <HeadToHead context={context} plans={plans} t={t} title={title("h2h")} short={(s) => teams[s].short_name} />
      </div>
    </section>
  );
}

/** The news first and widest with what could tip the players beside it, then the reunions; nothing without any. */
export function PreMatchStories() {
  const pre = usePre();
  if (!pre) return null;
  const { context, t, title, name, teamOf, fan } = pre;
  const news = context.news.filter((n) => n.public).sort((a, b) => a.hours_before_kickoff - b.hours_before_kickoff);
  // Ties across the two squads only: a reunion with an opponent is the story, not two teammates.
  const across = context.relationships.filter((r) => teamOf(r.person_id) && teamOf(r.other_id) && teamOf(r.person_id) !== teamOf(r.other_id));
  const reunions = strongest(context.effects, (e) => e.source === "former_club", MAX_TIES);
  const effects = strongest(context.effects, (e) => !TIE_SOURCES.has(e.source) && !ROUTINE_SOURCES.has(e.source) && e.delta !== 0, MAX_FACTORS);
  if (!news.length && !across.length && !reunions.length && !effects.length) return null;
  const people = { t, name, teamOf };
  return (
    <section className="post-sec" aria-labelledby="pre-stories-hd">
      <header className="sec-hd">
        <h2 id="pre-stories-hd">{t("pre.stories")}</h2>
        <p className="muted">{t("pre.storiesNote")}</p>
      </header>
      <div className="pre-stories">
        <News news={news} title={title("news")} {...people} />
        <Factors effects={effects} title={title("factors")} fan={fan} {...people} />
        <Ties across={across} reunions={reunions} title={title("ties")} {...people} />
      </div>
    </section>
  );
}

type Part = { t: T; title: string };
type NewsItem = MatchContext["news"][number];
type Relationship = MatchContext["relationships"][number];
type People = { name: (id: string) => string; teamOf: (id: string) => Side | undefined };

function Occasion({ context: c, t }: { context: MatchContext; t: T }) {
  const rows: [string, string][] = [
    [t("pre.competition"), c.competition.name],
    [t("pre.venue"), c.venue],
  ];
  if (c.attendance > 0) rows.push([t("pre.crowd"), c.attendance.toLocaleString()]);
  if (c.referee) rows.push([t("pre.referee"), c.referee.name]);
  rows.push([t("pre.weather"), t(`pre.weather.${c.weather}`)], [t("pre.pitch"), t(`pre.pitch.${c.pitch}`)]);
  const stakes = c.stakes === "none" ? null : c.stakes;
  return (
    <div className="pre-occasion">
      {(stakes || c.derby) && (
        <p className="pre-tags">
          {stakes && <span className="stamp line">{t(`pre.stakes.${stakes}`)}</span>}
          {c.derby && <span className="stamp line">{t("pre.derby")}</span>}
        </p>
      )}
      <dl className="pre-facts">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function Form({ form, t, title, name }: Part & { form: TeamForm[]; name: (s: Side) => string }) {
  const rows = SIDES.flatMap((s) => form.filter((f) => f.side === s));
  if (!rows.some((f) => f.last_results.length || f.league_position != null)) return null;
  const [h, a] = SIDES.map((s) => rows.find((f) => f.side === s)?.points);
  const gap = h != null && a != null && h !== a ? Math.abs(h - a) : null;
  return (
    <section className="pre-form" aria-labelledby="pre-form-hd">
      <h3 id="pre-form-hd">
        {title}
        {gap && <small>{t("pre.gap", { n: gap })}</small>}
      </h3>
      <div className="pre-teams">
        {rows.map((f) => (
          <div key={f.side} className={`pre-team ${f.side}`}>
            <span className="pre-name"><Kit side={f.side} />{name(f.side)}</span>
            {f.league_position != null && (
              <span className="pre-place">
                <b>{t("pre.place", { n: f.league_position, ord: ordinal(f.league_position) })}</b>
                {f.points != null && <small>{t("pre.points", { n: f.points })}</small>}
              </span>
            )}
            {f.last_results.length > 0 && (
              <>
                <ol className="pre-wdl" aria-label={t("pre.lastN", { n: f.last_results.length })}>
                  {f.last_results.map((r, i) => (
                    <li key={i} className={`r-${r}`} title={t(`pre.result.${r}`)}>
                      {t(`pre.res.${r}`)}
                    </li>
                  ))}
                </ol>
                <span className="pre-goals muted">
                  {t("pre.goals", { n: f.last_results.length, scored: f.goals_for_last5, conceded: f.goals_against_last5 })}
                </span>
              </>
            )}
          </div>
        ))}
      </div>
      <p className="pre-hint muted">{t("pre.newestLast")}</p>
    </section>
  );
}

function HeadToHead({ context, plans, t, title, short }: Part & {
  context: MatchContext; plans: Record<Side, TeamPlan>; short: (s: Side) => string;
}) {
  const h = context.head_to_head;
  if (!h || h.played === 0) return null;
  const sideOf = (club: string): Side | null => SIDES.find((s) => plans[s].club_id === club) ?? null;
  const label = (club: string) => {
    const s = sideOf(club);
    return s ? short(s) : club;
  };
  const parts: [string, number, string, string][] = [
    ["home", h.home_wins, t("pre.h2hWins", { team: short("home") }), t("pre.wins", { team: short("home"), n: h.home_wins })],
    ["draw", h.draws, t("pre.h2hDraws"), t("pre.draws", { n: h.draws })],
    ["away", h.away_wins, t("pre.h2hWins", { team: short("away") }), t("pre.wins", { team: short("away"), n: h.away_wins })],
  ];
  const winner = (m: PastMeeting) => (m.home_goals === m.away_goals ? null : m.home_goals > m.away_goals ? m.home_club_id : m.away_club_id);
  return (
    <section className="pre-h2h" aria-labelledby="pre-h2h-hd">
      <h3 id="pre-h2h-hd">
        {title}
        <small>{t("pre.played", { n: h.played })}</small>
      </h3>
      <ul className="pre-tally">
        {parts.map(([k, n, word, said]) => (
          <li key={k} className={k}>
            <b aria-hidden="true">{n}</b>
            <span aria-hidden="true">{word}</span>
            <span className="sr-only">{said}</span>
          </li>
        ))}
      </ul>
      <div className="pre-split" aria-hidden="true">
        {parts.map(([k, n]) => n > 0 && <i key={k} className={k} style={{ flexGrow: n }} />)}
      </div>
      {h.last_meetings.length > 0 && (
        <ol className="pre-meetings">
          {h.last_meetings.slice().reverse().map((m, i) => {
            const w = winner(m);
            return (
              <li key={i}>
                <span className="muted">{m.season}</span>
                <span className={w === m.home_club_id ? "won" : undefined}>{label(m.home_club_id)}</span>
                <b>{m.home_goals}–{m.away_goals}</b>
                <span className={w === m.away_club_id ? "won" : undefined}>{label(m.away_club_id)}</span>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

const when = (t: T, hours: number) => (hours < 48 ? t("pre.hoursBefore", { n: hours }) : t("pre.daysBefore", { n: Math.round(hours / 24) }));

function News({ news, t, title, name, teamOf }: Part & People & { news: NewsItem[] }) {
  if (!news.length) return null;
  return (
    <Card title={title} className="pre-news">
      <ul className="pre-feed">
        {news.map((n) => (
          <li key={n.news_id} className={`tone-${n.sentiment}`}>
            <p className="pre-meta">
              <span className="pre-who"><Kit side={teamOf(n.subject_id)} />{name(n.subject_id)}</span>
              <span className="pre-kind">{t(`pre.kind.${n.kind}`)}</span>
              {n.sentiment !== "neutral" && <span className={`pre-tone ${n.sentiment}`}>{t(`pre.tone.${n.sentiment}`)}</span>}
              <span className="pre-when muted">{when(t, n.hours_before_kickoff)}</span>
            </p>
            <p className="pre-headline">
              {n.headline} <LangTag lang="en" />
            </p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** The strongest effect behind each distinct note, strongest first. */
function strongest(effects: ContextEffect[], keep: (e: ContextEffect) => boolean, max: number): ContextEffect[] {
  const seen = new Set<string>();
  return effects
    .filter(keep)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
    .filter((e) => {
      const k = `${e.subject_id}|${e.note}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    })
    .slice(0, max);
}

function Factors({ effects, t, title, name, teamOf, fan }: Part & People & { effects: ContextEffect[]; fan: boolean }) {
  if (!effects.length) return null;
  return (
    <Card title={title} note={t("pre.factorsNote")} className="pre-factors">
      <ul className="pre-list">
        {effects.map((e) => (
          <li key={e.effect_id}>
            <span className={`pre-chip ${e.delta > 0 ? "up" : "down"}`}>
              {t(`pre.target.${e.target}`)} {e.delta > 0 ? "▲" : "▼"}
              {!fan && <small> {e.delta > 0 ? "+" : "−"}{Math.abs(e.delta * 100).toFixed(1)}%</small>}
            </span>
            <span>
              <b className="pre-who"><Kit side={teamOf(e.subject_id)} />{name(e.subject_id)}</b>
              <span className="pre-note">{e.note} <LangTag lang="en" /></span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Ties({ across, reunions, t, title, name, teamOf }: Part & People & { across: Relationship[]; reunions: ContextEffect[] }) {
  if (!across.length && !reunions.length) return null;
  return (
    <Card title={title} className="pre-ties">
      <ul className="pre-list">
        {reunions.map((e) => (
          <li key={e.effect_id}>
            <span className="pre-chip">{t("pre.formerClub")}</span>
            <span>
              <b className="pre-who"><Kit side={teamOf(e.subject_id)} />{name(e.subject_id)}</b>
              <span className="pre-note">{e.note} <LangTag lang="en" /></span>
            </span>
          </li>
        ))}
        {across.slice(0, MAX_TIES).map((r) => (
          <li key={r.relationship_id}>
            <span className="pre-chip">{t(`pre.tie.${r.kind}`)}</span>
            <span>
              <span className="pre-pair">
                <b className="pre-who"><Kit side={teamOf(r.person_id)} />{name(r.person_id)}</b>
                <span aria-hidden="true">↔</span>
                <b className="pre-who"><Kit side={teamOf(r.other_id)} />{name(r.other_id)}</b>
              </span>
              {r.shared_seasons > 0 && <span className="pre-note muted">{t("pre.seasons", { n: r.shared_seasons })}</span>}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
