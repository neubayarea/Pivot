// The deeper pre-match data (#315, data from #314): each side's home and away record with the one
// that counts today marked, the results at this ground, the last five with half-time scores, the
// last five in numbers, and what each side plays next with how many regulars sit out today.
// Home reads on the left and away on the right, as everywhere on the tab; with a ♥ team picked its
// side is "your team" and its numbers carry the kit colour, the other side's go grey. Fans get the
// story and four numbers; analysts the full tables and the goals by period. A part the API has no
// data for is left out, never shown as zeros.
import { useMatch, type Side } from "../data/match";
import { usePersona } from "../data/persona";
import {
  PERIODS, gameTags, played, usePreMatchReport,
  type Meeting, type NextFixture, type PreMatchReport, type RecentGame, type RecentStats, type TeamPreMatch, type TeamRecord, type UsualXi,
} from "../data/prematch";
import { isMessageKey, usePrefs, type MessageKey, type T } from "../i18n";
import Card from "./Card";
import LangTag from "./LangTag";
import { Kit } from "./PreMatch";
import "../styles/prematch.css";

const SIDES: Side[] = ["home", "away"];

/** Fetches `/prematch` for the match on screen; nothing until it answers, nothing when it cannot. */
export default function PreMatchDeep() {
  const { match } = useMatch();
  const { data } = usePreMatchReport(match.match_id);
  return data ? <PreMatchDeepView report={data} /> : null;
}

type Ctx = {
  t: T; fan: boolean; names: (list: string[]) => string; mine: Side | null; num: (n: number, digits?: number) => string;
  name: (s: Side) => string; short: (s: Side) => string; playerName: (id: string) => string;
};

/** The four blocks from one report; split out so tests can render it without a fetch. */
export function PreMatchDeepView({ report }: { report: PreMatchReport }) {
  const { teams, playerName, preMatch } = useMatch();
  const { prefs, t } = usePrefs();
  const { fan, side: mine } = usePersona();
  const locale = prefs.language === "zh" ? "zh-CN" : prefs.language;
  const ctx: Ctx = {
    t, fan, mine, playerName, names: (list) => list.join(prefs.language === "zh" ? "、" : ", "),
    num: (n, digits = 1) => n.toLocaleString(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits }),
    name: (s) => teams[s].name, short: (s) => teams[s].short_name,
  };
  const title = (key: string) => t((fan ? `pre.fan.${key}` : `pre.${key}`) as MessageKey);
  const at = report.teams;
  const homeClub = preMatch?.plans.home.club_id ?? null;
  // Fans read the story first: who rests players, then how the last games went; analysts the record first.
  const blocks = [
    <Venue key="venue" at={at} h2h={report.head_to_head} homeClub={homeClub} venue={preMatch?.context.venue ?? null} title={title("venueRecord")} {...ctx} />,
    <LastFive key="last5" at={at} title={title("last5")} {...ctx} />,
    <Numbers key="numbers" at={at} title={title("numbers")} {...ctx} />,
    <NextUp key="next" at={at} title={title("nextUp")} {...ctx} />,
  ];
  const order = fan ? [3, 1, 2, 0] : [0, 1, 2, 3];
  if (!SIDES.some((s) => hasAny(at[s])) && !report.head_to_head?.at_this_ground?.played) return null;
  return (
    <section className="post-sec pre-deep" aria-labelledby="pre-deep-hd">
      <header className="sec-hd">
        <h2 id="pre-deep-hd">{title("deep")}</h2>
        <p className="muted">{t(mine ? "pre.deepNoteMine" : "pre.deepNote", { team: mine ? teams[mine].name : "" })}</p>
      </header>
      <div className="pre-deep-grid">{order.map((i) => blocks[i])}</div>
    </section>
  );
}

const hasAny = (x: TeamPreMatch | null) =>
  !!x && (played(x.overall) || x.last5.length > 0 || !!x.next_fixture || !!x.usual_xi_today);

/** "Your team" / "Opponent" under a team's name when a ♥ team is picked. */
function TeamHead({ side, t, mine, name }: Pick<Ctx, "t" | "mine" | "name"> & { side: Side }) {
  return (
    <p className={`pre-dh ${side}`}>
      <span className="pre-name"><Kit side={side} />{name(side)}</span>
      {mine && <span className="pre-role">{t(mine === side ? "pre.yourTeam" : "pre.opponent")}</span>}
    </p>
  );
}

/** "mine" / "theirs" on a team's block, so the picked team keeps its kit colour and the other goes grey. */
const pickClass = (side: Side, mine: Side | null) => (mine === null ? "" : mine === side ? " mine" : " theirs");

// 1. Home and away. ------------------------------------------------------------------------------

type Split = "overall" | "home_only" | "away_only";
/** The split that counts in this match: the home side at home, the away side away. */
const today: Record<Side, Split> = { home: "home_only", away: "away_only" };

function Venue({ at, h2h, homeClub, venue, title, ...c }: Ctx & {
  at: PreMatchReport["teams"]; h2h: PreMatchReport["head_to_head"]; homeClub: string | null; venue: string | null; title: string;
}) {
  const sides = SIDES.filter((s) => played(at[s]?.overall) || played(at[s]?.[today[s]]));
  const ground = h2h?.at_this_ground;
  const meetings = (h2h?.meetings ?? []).filter((m) => homeClub && m.venue_club === homeClub).slice().reverse();
  if (!sides.length && !ground?.played) return null;
  return (
    <Card title={title} className="pre-venue">
      {sides.length > 0 && (
        <div className="pre-cols">
          {sides.map((s) => (
            <div key={s} className={`pre-col ${s}${pickClass(s, c.mine)}`}>
              <TeamHead side={s} {...c} />
              {c.fan ? <VenueLine side={s} rec={at[s]![today[s]]} {...c} /> : <RecordTable side={s} team={at[s]!} {...c} />}
            </div>
          ))}
        </div>
      )}
      {ground && ground.played > 0 && venue && <Ground ground={ground} meetings={meetings} venue={venue} {...c} />}
    </Card>
  );
}

/** Fan mode: one sentence for the split that counts today. */
function VenueLine({ side, rec, t, name }: Ctx & { side: Side; rec: TeamRecord | null }) {
  if (!played(rec)) return null;
  return <p className="pre-line now">{t(side === "home" ? "pre.atHomeLine" : "pre.awayLine", { team: name(side), w: rec.w, d: rec.d, l: rec.l })}</p>;
}

function RecordTable({ side, team, t, num }: Ctx & { side: Side; team: TeamPreMatch }) {
  const rows = (["overall", "home_only", "away_only"] as Split[]).filter((k) => played(team[k]));
  if (!rows.length) return null;
  return (
    <table className="pre-rec num">
      <thead>
        <tr>
          <th scope="col"><span className="sr-only">{t("pre.rec.split")}</span></th>
          {(["p", "w", "d", "l", "gf", "ga", "pts", "ppg"] as const).map((k) => (
            <th key={k} scope="col"><abbr title={t(`pre.rec.${k}.long`)}>{t(`pre.rec.${k}`)}</abbr></th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((k) => {
          const r = team[k]!;
          const now = today[side] === k;
          return (
            <tr key={k} className={now ? "now" : undefined}>
              <th scope="row">
                {t(`pre.rec.${k}`)}
                {now && <small>{t("pre.rec.today")}</small>}
              </th>
              <td>{r.played}</td><td>{r.w}</td><td>{r.d}</td><td>{r.l}</td><td>{r.gf}</td><td>{r.ga}</td>
              <td><b>{r.pts}</b></td><td>{num(r.ppg, 2)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** The meetings at this match's ground: the tally, then each with its half-time score. */
function Ground({ ground, meetings, venue, t, short, mine }: Ctx & { ground: NonNullable<NonNullable<PreMatchReport["head_to_head"]>["at_this_ground"]>; meetings: Meeting[]; venue: string }) {
  const parts: [string, string][] = [
    ["home", t("pre.wins", { team: short("home"), n: ground.home_w })],
    ["draw", t("pre.draws", { n: ground.d })],
    ["away", t("pre.wins", { team: short("away"), n: ground.away_w })],
  ];
  const won = (m: Meeting): Side | null => (m.ft[0] === m.ft[1] ? null : m.ft[0] > m.ft[1] ? "home" : "away");
  return (
    <section className="pre-ground" aria-labelledby="pre-ground-hd">
      <h4 id="pre-ground-hd">
        {t("pre.atGround", { venue })}
        <small>{t("pre.played", { n: ground.played })}</small>
      </h4>
      <p className="pre-ground-tally">
        {parts.map(([k, said]) => (
          <span key={k} className={`${k}${k !== "draw" ? pickClass(k as Side, mine) : ""}`}>
            {k !== "draw" && <Kit side={k as Side} />}
            {said}
          </span>
        ))}
      </p>
      {meetings.length > 0 && (
        <ol className="pre-meetings">
          {meetings.map((m, i) => {
            const w = won(m);
            return (
              <li key={i}>
                <span className="muted">{m.season}</span>
                <span className={w === "home" ? "won" : undefined}>{short("home")}</span>
                <b>{m.ft[0]}–{m.ft[1]}</b>
                <span className={w === "away" ? "won" : undefined}>{short("away")}</span>
                {m.ht && <small className="muted">{t("pre.htShort", { score: `${m.ht[0]}–${m.ht[1]}` })}</small>}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

// 2. The last five with half-time scores. --------------------------------------------------------

function LastFive({ at, title, ...c }: Ctx & { at: PreMatchReport["teams"]; title: string }) {
  const sides = SIDES.filter((s) => (at[s]?.last5.length ?? 0) > 0);
  if (!sides.length) return null;
  return (
    <Card title={title} note={c.t("pre.newestFirst")} className="pre-last5">
      <div className="pre-cols">
        {sides.map((s) => (
          <div key={s} className={`pre-col ${s}${pickClass(s, c.mine)}`}>
            <TeamHead side={s} {...c} />
            <ol className="pre-games">
              {at[s]!.last5.slice().reverse().map((g) => <Game key={g.matchday} g={g} {...c} />)}
            </ol>
          </div>
        ))}
      </div>
    </Card>
  );
}

function Game({ g, t }: Ctx & { g: RecentGame }) {
  const tags = gameTags(g);
  return (
    <li>
      <span className={`pre-res r-${g.result}`} title={t(`pre.result.${g.result}`)}>{t(`pre.res.${g.result}`)}</span>
      <span className="pre-game">
        <span className="pre-opp">{t(g.venue === "H" ? "pre.vsHome" : "pre.vsAway", { team: g.opponent })}</span>
        <span className="pre-score num">
          {g.ht && <span className="muted">{t("pre.htShort", { score: `${g.ht[0]}–${g.ht[1]}` })}</span>}
          <b>{t("pre.ftShort", { score: `${g.ft[0]}–${g.ft[1]}` })}</b>
        </span>
        {tags.length > 0 && (
          <span className="pre-gtags">
            {tags.map((k) => <span key={k} className={`pre-chip tag-${k}`}>{t(`pre.tag.${k}`)}</span>)}
          </span>
        )}
      </span>
    </li>
  );
}

// 3. The last five in numbers. -------------------------------------------------------------------

type StatKey = Exclude<keyof RecentStats, "goals_by_period" | "conceded_by_period" | "ht_lead_won" | "ht_lead_dropped">;
/** Averages run to the larger side's value (at least 2 a game); counts are out of the games played. */
const AVERAGES = new Set<StatKey>(["gf_avg", "ga_avg", "avg_rating"]);
const FAN_STATS: StatKey[] = ["gf_avg", "ga_avg", "clean_sheets", "scored_first"];
const ALL_STATS: StatKey[] = ["gf_avg", "ga_avg", "clean_sheets", "failed_to_score", "btts", "over_2_5", "scored_first", "reds", "avg_rating"];

function Numbers({ at, title, ...c }: Ctx & { at: PreMatchReport["teams"]; title: string }) {
  const { t, fan, mine, num } = c;
  const stats = (s: Side) => at[s]?.last5_stats ?? null;
  const games = (s: Side) => at[s]?.last5.length || 5;
  const rows = (fan ? FAN_STATS : ALL_STATS).filter((k) => SIDES.some((s) => stats(s)?.[k] != null));
  const periods = !fan && SIDES.some((s) => stats(s)?.goals_by_period || stats(s)?.conceded_by_period);
  if (!rows.length && !periods) return null;
  const shown = (k: StatKey, s: Side) => {
    const v = stats(s)?.[k];
    if (v == null) return null;
    if (AVERAGES.has(k)) return num(v);
    return t("pre.ofN", { n: v, of: games(s) });
  };
  const scale = (k: StatKey, s: Side) => {
    const v = stats(s)?.[k];
    if (v == null) return 0;
    if (k === "avg_rating") return Math.max(0, Math.min(1, (v - 5) / 3));
    if (AVERAGES.has(k)) return v / Math.max(2, ...SIDES.map((x) => stats(x)?.[k] ?? 0));
    return v / games(s);
  };
  return (
    <Card title={title} note={t("pre.numbersNote")} className="pre-numbers">
      {rows.length > 0 && (
        <div className="pre-bars" role="table" aria-label={title}>
          <div className="pre-bars-hd" role="row">
            {SIDES.map((s) => (
              <span key={s} role="columnheader" className={`${s}${pickClass(s, mine)}`}>
                <Kit side={s} />{c.short(s)}
                {mine === s && <small>{t("pre.yourTeam")}</small>}
              </span>
            ))}
          </div>
          {rows.map((k) => (
            <div key={k} className="pre-bar-row" role="row">
              <span className="nm" role="rowheader">{t((fan ? `pre.fan.stat.${k}` : `pre.stat.${k}`) as MessageKey)}</span>
              {SIDES.map((s) => (
                <span key={s} role="cell" className={`pre-bar-val ${s}${pickClass(s, mine)}`}>
                  <b>{shown(k, s) ?? "–"}</b>
                  {shown(k, s) !== null && (
                    <i className="pre-bar" aria-hidden="true"><i style={{ width: `${Math.round(scale(k, s) * 100)}%` }} /></i>
                  )}
                </span>
              ))}
            </div>
          ))}
        </div>
      )}
      {periods && (
        <div className="pre-cols pre-periods-wrap">
          {SIDES.filter((s) => stats(s)?.goals_by_period || stats(s)?.conceded_by_period).map((s) => (
            <Periods key={s} side={s} stats={stats(s)!} {...c} />
          ))}
        </div>
      )}
    </Card>
  );
}

/** Goals scored (up, kit colour) and conceded (down, grey) in each quarter-hour, as a small chart. */
function Periods({ side, stats, t, mine, short }: Ctx & { side: Side; stats: RecentStats }) {
  const scored = stats.goals_by_period ?? {};
  const let_in = stats.conceded_by_period ?? {};
  const top = Math.max(1, ...PERIODS.map((p) => Math.max(scored[p] ?? 0, let_in[p] ?? 0)));
  return (
    <figure className={`pre-periods ${side}${pickClass(side, mine)}`}>
      <figcaption>
        <Kit side={side} />
        {t("pre.byPeriod", { team: short(side) })}
      </figcaption>
      <div className="pre-pchart" aria-hidden="true">
        {PERIODS.map((p) => (
          <div key={p} className="pre-pcol">
            <span className="up"><b>{scored[p] ?? ""}</b><i style={{ height: `${((scored[p] ?? 0) / top) * 40}px` }} /></span>
            <span className="down"><i style={{ height: `${((let_in[p] ?? 0) / top) * 40}px` }} /><b>{let_in[p] ?? ""}</b></span>
            <small>{p.replace("-", "–")}</small>
          </div>
        ))}
      </div>
      <p className="pre-plegend muted" aria-hidden="true">
        <span className="up">{t("pre.scored")}</span>
        <span className="down">{t("pre.conceded")}</span>
      </p>
      <table className="sr-only">
        <thead>
          <tr>
            <th scope="col">{t("pre.minutes")}</th>
            <th scope="col">{t("pre.scored")}</th>
            <th scope="col">{t("pre.conceded")}</th>
          </tr>
        </thead>
        <tbody>
          {PERIODS.map((p) => (
            <tr key={p}><th scope="row">{p}</th><td>{scored[p] ?? "–"}</td><td>{let_in[p] ?? "–"}</td></tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

// 4. What comes next, and who rests. -------------------------------------------------------------

function NextUp({ at, title, ...c }: Ctx & { at: PreMatchReport["teams"]; title: string }) {
  const sides = SIDES.filter((s) => at[s]?.next_fixture || at[s]?.usual_xi_today);
  if (!sides.length) return null;
  const madeUp = sides.some((s) => at[s]?.next_fixture?.fictional);
  return (
    <Card title={title} className="pre-next">
      <div className="pre-cols">
        {sides.map((s) => (
          <div key={s} className={`pre-col ${s}${pickClass(s, c.mine)}`}>
            <TeamHead side={s} {...c} />
            {at[s]!.next_fixture && <Fixture side={s} f={at[s]!.next_fixture!} {...c} />}
            {at[s]!.usual_xi_today && <Rotation side={s} xi={at[s]!.usual_xi_today!} {...c} />}
          </div>
        ))}
      </div>
      <p className="pre-hint muted">
        {c.t("pre.nextNote")}
        {madeUp && ` ${c.t("pre.nextMadeUp")}`}
      </p>
    </Card>
  );
}

/** "Quarter-final" in the page's language when we have it; the API's English otherwise, tagged. */
function Stage({ stage, t }: { stage: string; t: T }) {
  const key = `pre.stage.${stage.toLowerCase().replace(/[^a-z0-9]+/g, "_")}`;
  return isMessageKey(key) ? <>{t(key)}</> : <>{stage} <LangTag lang="en" /></>;
}

function Fixture({ f, t, fan }: Ctx & { side: Side; f: NextFixture }) {
  return (
    <div className="pre-fixture">
      <p className="pre-fx-what">
        <b>{f.competition}</b>
        {f.stage && <> <Stage stage={f.stage} t={t} /></>}
      </p>
      <p className="pre-line">
        {t(f.venue === "H" ? "pre.nextHome" : "pre.nextAway", { team: f.opponent })}{" "}
        <b className="num">{t("pre.inDays", { n: f.days_until })}</b>
      </p>
      {fan ? (
        f.rotation_risk !== "low" && <p className="pre-line">{t(`pre.fan.risk.${f.rotation_risk}`)}</p>
      ) : (
        <dl className="pre-facts">
          <div><dt>{t("pre.importance")}</dt><dd>{t(`pre.level.${f.importance}`)}</dd></div>
          <div><dt>{t("pre.rotationRisk")}</dt><dd>{t(`pre.level.${f.rotation_risk}`)}</dd></div>
        </dl>
      )}
    </div>
  );
}

/** How many of the usual starters begin today, who sits out, who comes in; worked out from the season. */
function Rotation({ side, xi, t, playerName, name, names }: Ctx & { side: Side; xi: UsualXi }) {
  const benched = xi.regulars_benched.map(playerName);
  const fresh = xi.newcomers.map(playerName);
  return (
    <div className="pre-rotation">
      <p className="pre-line">
        {benched.length
          ? t("pre.rotated", { team: name(side), n: benched.length, starting: xi.regulars_starting })
          : t("pre.unchanged", { team: name(side) })}
      </p>
      {benched.length > 0 && (
        <dl className="pre-facts pre-who-list">
          <div><dt>{t("pre.benched")}</dt><dd>{names(benched)}</dd></div>
          {fresh.length > 0 && <div><dt>{t("pre.inFor")}</dt><dd>{names(fresh)}</dd></div>}
        </dl>
      )}
    </div>
  );
}
