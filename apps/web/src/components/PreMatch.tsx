// The pre-match tab (Ax60): what the API sends about the match before kick-off and the page used to
// drop (#276): the occasion, form and table, head-to-head, the news, what could tip the players, and
// the ties between the two squads. One card per subject; a subject the match has no data for is left
// out, never shown as zeros. Headlines and effect notes are written by the simulator in English.
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

export default function PreMatch() {
  const { preMatch, teams, squads, playerName } = useMatch();
  const { prefs, t } = usePrefs();
  if (!preMatch) return null;
  const { context, plans } = preMatch;
  const fan = prefs.audience === "fan";
  // Fan mode titles the same cards in plain words, as the stats do.
  const title = (key: string) => t((fan ? `pre.fan.${key}` : `pre.${key}`) as MessageKey);
  const coaches = new Map(SIDES.map((s) => [plans[s].coach.coach_id, plans[s].coach.name]));
  const teamOf = new Map<string, Side>(SIDES.flatMap((s) => [
    [plans[s].coach.coach_id, s] as const, ...squads[s].map((p) => [p.player_id, s] as const),
  ]));
  const name = (id: string) => (id === "home" || id === "away" ? teams[id].name : (coaches.get(id) ?? playerName(id)));

  return (
    <div className="prematch">
      <Occasion context={context} t={t} title={title("occasion")} />
      <Form form={context.form} t={t} title={title("form")} name={(s) => teams[s].name} />
      <HeadToHead context={context} plans={plans} t={t} title={title("h2h")} short={(s) => teams[s].short_name} />
      <News context={context} t={t} title={title("news")} name={name} />
      <Factors context={context} t={t} title={title("factors")} name={name} fan={fan} />
      <Ties context={context} t={t} title={title("ties")} name={name} teamOf={(id) => teamOf.get(id)} />
    </div>
  );
}

type Part = { t: T; title: string };

function Occasion({ context: c, t, title }: Part & { context: MatchContext }) {
  const rows: [string, string][] = [
    [t("pre.competition"), c.competition.name],
    [t("pre.venue"), c.venue],
  ];
  if (c.attendance > 0) rows.push([t("pre.crowd"), c.attendance.toLocaleString()]);
  if (c.referee) rows.push([t("pre.referee"), c.referee.name]);
  rows.push([t("pre.weather"), t(`pre.weather.${c.weather}`)], [t("pre.pitch"), t(`pre.pitch.${c.pitch}`)]);
  const stakes = c.stakes === "none" ? null : c.stakes;
  return (
    <Card title={title} className="pre-occasion">
      {(stakes || c.derby) && (
        <p className="pre-tags">
          {c.derby && <span className="stamp line">{t("pre.derby")}</span>}
          {stakes && <span className="stamp live">{t(`pre.stakes.${stakes}`)}</span>}
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
    </Card>
  );
}

function Form({ form, t, title, name }: Part & { form: TeamForm[]; name: (s: Side) => string }) {
  const rows = SIDES.flatMap((s) => form.filter((f) => f.side === s));
  if (!rows.some((f) => f.last_results.length || f.league_position != null)) return null;
  const [h, a] = SIDES.map((s) => rows.find((f) => f.side === s)?.points);
  const gap = h != null && a != null && h !== a ? Math.abs(h - a) : null;
  return (
    <Card title={title} note={gap ? t("pre.gap", { n: gap }) : undefined} className="pre-form">
      {rows.map((f) => (
        <div key={f.side} className={`pre-team ${f.side}`}>
          <span className="pre-name">{name(f.side)}</span>
          {f.league_position != null && (
            <span className="pre-place">
              {t("pre.place", { n: f.league_position, ord: ordinal(f.league_position) })}
              {f.points != null && <small> · {t("pre.points", { n: f.points })}</small>}
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
      <p className="pre-hint muted">{t("pre.newestLast")}</p>
    </Card>
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
  const parts: [string, number, string][] = [
    ["home", h.home_wins, t("pre.wins", { team: short("home"), n: h.home_wins })],
    ["draw", h.draws, t("pre.draws", { n: h.draws })],
    ["away", h.away_wins, t("pre.wins", { team: short("away"), n: h.away_wins })],
  ];
  const winner = (m: PastMeeting) => (m.home_goals === m.away_goals ? null : m.home_goals > m.away_goals ? m.home_club_id : m.away_club_id);
  return (
    <Card title={title} note={t("pre.played", { n: h.played })} className="pre-h2h">
      <div className="pre-split" aria-hidden="true">
        {parts.map(([k, n]) => n > 0 && <i key={k} className={k} style={{ flexGrow: n }}>{n}</i>)}
      </div>
      <p className="pre-split-key">{parts.map(([k, , text]) => <span key={k} className={k}>{text}</span>)}</p>
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
    </Card>
  );
}

const when = (t: T, hours: number) => (hours < 48 ? t("pre.hoursBefore", { n: hours }) : t("pre.daysBefore", { n: Math.round(hours / 24) }));

function News({ context, t, title, name }: Part & { context: MatchContext; name: (id: string) => string }) {
  const news = context.news.filter((n) => n.public).sort((a, b) => a.hours_before_kickoff - b.hours_before_kickoff);
  if (!news.length) return null;
  return (
    <Card title={title} className="pre-news">
      <ul className="pre-list">
        {news.map((n) => (
          <li key={n.news_id} className={`tone-${n.sentiment}`}>
            <span className="pre-dot" aria-label={t(`pre.tone.${n.sentiment}`)} />
            <span>
              {n.headline} <LangTag lang="en" />
              <small className="muted">{name(n.subject_id)} · {t(`pre.kind.${n.kind}`)} · {when(t, n.hours_before_kickoff)}</small>
            </span>
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

function Factors({ context, t, title, name, fan }: Part & { context: MatchContext; name: (id: string) => string; fan: boolean }) {
  const effects = strongest(context.effects, (e) => !TIE_SOURCES.has(e.source) && !ROUTINE_SOURCES.has(e.source) && e.delta !== 0, MAX_FACTORS);
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
              <b>{name(e.subject_id)}</b> · {e.note} <LangTag lang="en" />
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Ties({ context, t, title, name, teamOf }: Part & {
  context: MatchContext; name: (id: string) => string; teamOf: (id: string) => Side | undefined;
}) {
  // Ties across the two squads only: a reunion with an opponent is the story, not two teammates.
  const across = context.relationships.filter((r) => teamOf(r.person_id) && teamOf(r.other_id) && teamOf(r.person_id) !== teamOf(r.other_id));
  const reunions = strongest(context.effects, (e) => e.source === "former_club", MAX_TIES);
  if (!across.length && !reunions.length) return null;
  return (
    <Card title={title} className="pre-ties">
      <ul className="pre-list">
        {reunions.map((e) => (
          <li key={e.effect_id}>
            <span className="pre-chip">{t("pre.formerClub")}</span>
            <span>
              <b>{name(e.subject_id)}</b> · {e.note} <LangTag lang="en" />
            </span>
          </li>
        ))}
        {across.slice(0, MAX_TIES).map((r) => (
          <li key={r.relationship_id}>
            <span className="pre-chip">{t(`pre.tie.${r.kind}`)}</span>
            <span>
              <b>{name(r.person_id)}</b> ↔ <b>{name(r.other_id)}</b>
              {r.shared_seasons > 0 && <small className="muted">{t("pre.seasons", { n: r.shared_seasons })}</small>}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
