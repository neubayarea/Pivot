// 阵容 · Line-ups (C13 #316 tab, Ax69 #322 content): both XIs in their formations with a ☆ to follow any player,
// the line-up seen from the viewer's ♥ team (its lines against theirs, where it has a spare man and
// where it is short, and how the two plans differ, data/matchup.ts), and each coach's plan.
// With a team picked that team attacks up the pitch; without one the matchup asks for a team.
import type { CSSProperties } from "react";
import FollowTeam from "../../components/FollowTeam";
import Lineups from "../../components/Lineups";
import TeamTactics from "../../components/TeamTactics";
import { AveragePositions, VizBox, useAveragePositions } from "../../components/viz";
import { useMatch, type Side } from "../../data/match";
import { lines, tacticsDiff, type ApiLine, type Diff } from "../../data/matchup";
import { other, usePersona } from "../../data/persona";
import { useVizData } from "../../data/viz";
import { useT, type MessageKey, type T } from "../../i18n";

/** What #314's `GET /api/matches/{id}/prematch` sends that this tab reads; until it is merged the request 404s and the sheets are used. */
type Prematch = { matchup?: { lines?: ApiLine[] } };

function diffLine(d: Diff, t: T, team: string, opp: string, fan: boolean): string {
  if (d.field === "counter_attack") return t(d.mine ? "mu.counter.mine" : "mu.counter.theirs", { team, opp });
  if (d.field === "attack_focus") {
    return t("mu.attack_focus", {
      team, opp,
      mine: t(`mu.lane.${d.mine}`), theirs: t(`mu.lane.${d.theirs}`),
    });
  }
  const name = t((fan ? `plan.fan.${d.field}` : `plan.${d.field}`) as MessageKey);
  return t(`mu.${d.field}.${d.more ? "more" : "less"}` as MessageKey, {
    team, opp, what: name,
    mine: t(`plan.${d.field}.${d.mine}` as MessageKey).toLowerCase(), theirs: t(`plan.${d.field}.${d.theirs}` as MessageKey).toLowerCase(),
  });
}

function Matchup({ side }: { side: Side }) {
  const { match, teams, sheets, preMatch } = useMatch();
  const t = useT();
  const { fan } = usePersona();
  const api = useVizData<Prematch>(`/api/matches/${encodeURIComponent(match.match_id)}/prematch`);
  const opp = other(side);
  const team = teams[side].name;
  const them = teams[opp].name;
  const rows = sheets ? lines(sheets, side, api.data?.matchup?.lines) : [];
  const diffs = preMatch ? tacticsDiff({ home: preMatch.plans.home.tactics, away: preMatch.plans.away.tactics }, side) : [];
  if (!rows.length && !diffs.length) return <p className="muted">{t("mu.none")}</p>;
  return (
    <div className="mu" style={{ "--tc": `var(--pv-${side})`, "--oc": `var(--pv-${opp})` } as CSSProperties}>
      {rows.length > 0 && (
        <div className="mu-lines">
          <h3>{sheets ? t("mu.shapes", { team, mine: sheets[side].formation, opp: them, theirs: sheets[opp].formation }) : null}</h3>
          <ul>
            {rows.map((l) => (
              <li key={l.zone} className={`mu-line ${l.edge}`}>
                <span className="mu-zone">{t(`mu.zone.${l.zone}`)}</span>
                <span className="mu-roles mine">{l.mine.map((r, i) => <i key={i}>{r}</i>)}</span>
                <span className="mu-count num">{t("mu.count", { mine: l.mine.length, theirs: l.theirs.length })}</span>
                <span className="mu-roles theirs">{l.theirs.map((r, i) => <i key={i}>{r}</i>)}</span>
                <span className={`mu-edge ${l.edge}`}>{t(`mu.edge.${l.edge}`, { team, opp: them })}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {diffs.length > 0 && (
        <div className="mu-diffs">
          <h3>{t("mu.diffs")}</h3>
          <ul>
            {diffs.map((d) => <li key={d.field}>{diffLine(d, t, team, them, fan)}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

export function LineupsTab() {
  const t = useT();
  // The coach's plan below names each shape; the lists then leave it out.
  const { preMatch, match } = useMatch();
  const { side, fan } = usePersona();
  return (
    <div className="post lineups-tab">
      <section className="post-sec" aria-labelledby="lu-side-hd" id="lu-side">
        <header className="sec-hd">
          <h2 id="lu-side-hd">{t("mu.title")}</h2>
          <p className="muted">{t(side ? "mu.note" : "mu.pick")}</p>
        </header>
        {side ? <Matchup side={side} /> : (
          <p className="mu-pick">
            <FollowTeam side="home" withName />
            <FollowTeam side="away" withName />
          </p>
        )}
      </section>
      <section className="post-sec" aria-labelledby="lu-xi-hd" id="lu-xi">
        <header className="sec-hd">
          <h2 id="lu-xi-hd">{t("pre.lineups")}</h2>
          <p className="muted">{t("lu.note")}</p>
        </header>
        <Lineups up={side ?? "home"} follow facts formation={!preMatch} />
      </section>
      {!fan && match.status !== "scheduled" && <PaperVsActual />}
      <TeamTactics />
    </div>
  );
}

/**
 * C18 (#366): the analyst's "on paper vs where they played": each side's formation from the team
 * sheet beside the average positions the pictures API gives (the same picture as the Stats tab's).
 */
function PaperVsActual() {
  const t = useT();
  const { match, teams, sheets, squads } = useMatch();
  const pos = useAveragePositions(match.match_id, { stepS: 60 });
  const names = { home: teams.home.name, away: teams.away.name };
  return (
    <section className="post-sec" aria-labelledby="lu-real-hd" id="lu-real">
      <header className="sec-hd">
        <h2 id="lu-real-hd">{t("lu.realTitle")}</h2>
        <p className="muted">{t("lu.realNote", {
          home: teams.home.short_name, away: teams.away.short_name,
          hf: sheets?.home.formation ?? "–", af: sheets?.away.formation ?? "–",
        })}</p>
      </header>
      <div className="card lu-real">
        <VizBox state={pos}>{(d) => <AveragePositions data={d} squads={squads} teamNames={names} />}</VizBox>
      </div>
    </section>
  );
}
