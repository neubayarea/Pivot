// 阵容 · Line-ups (C13 #316 tab, Ax69 #322 content): both XIs in their formations with a ☆ to follow any player,
// the line-up seen from the viewer's ♥ team (its lines against theirs, where it has a spare man and
// where it is short, and how the two plans differ, data/matchup.ts), and each coach's plan.
// With a team picked that team attacks up the pitch; without one the matchup asks for a team.
// C21 (#401): analysts also get a card for each player on the pitch (minutes, rating, three stats for
// the role), what each substitution changed and the squad's ratings in bands; fans get the formation
// with ratings, the player of the match and the substitutions.
import type { CSSProperties } from "react";
import FollowTeam from "../../components/FollowTeam";
import Lineups from "../../components/Lineups";
import { FanLineupExtras, PlayerHoverCard, RatingSpread, SubImpactTable } from "../../components/LineupsMore";
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
  const played = match.status !== "scheduled";
  if (fan) {
    return (
      <div className="post lineups-tab">
        <section className="post-sec" aria-labelledby="lu-xi-hd" id="lu-xi">
          <header className="sec-hd">
            <h2 id="lu-xi-hd">{t("pre.lineups")}</h2>
            <p className="muted">{t("lu.note")}</p>
          </header>
          <Lineups up={side ?? "home"} follow facts formation />
        </section>
        {played && <FanLineupExtras />}
      </div>
    );
  }
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
        <Lineups up={side ?? "home"} follow facts formation={!preMatch} card={(p) => <PlayerHoverCard p={p} />} />
      </section>
      {played && <SubImpactTable />}
      {played && <RatingSpread />}
      {played && <PaperVsActual />}
      <TeamTactics />
    </div>
  );
}

const SIDES = ["home", "away"] as const;

/**
 * Each starter's slot in the formation on paper ("4-2-3-1": the keeper, then one row per number, back
 * to front, each row left to right), in metres in the team's own frame, attacking to the right, as
 * the average positions are. Empty when the sheet's slots do not add up to its formation.
 */
export function paperSlots(sheet: { formation: string; starters: readonly { player_id: string; slot: number }[] }): Map<string, [number, number]> {
  const rows = [1, ...sheet.formation.split("-").map(Number)];
  const slots = [...sheet.starters].sort((a, b) => a.slot - b.slot);
  const out = new Map<string, [number, number]>();
  if (rows.some((n) => !Number.isInteger(n) || n < 1) || rows.reduce((n, r) => n + r, 0) !== slots.length) return out;
  let i = 0;
  rows.forEach((count, row) => {
    for (let k = 0; k < count; k++, i++) {
      const depth = row === 0 ? 5 : 20 + ((row - 1) * 48) / Math.max(1, rows.length - 2);
      // The team's left is the far touchline when it attacks to the right.
      out.set(slots[i].player_id, [depth, 68 - (68 * (k + 1)) / (count + 1)]);
    }
  });
  return out;
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
  const starters = new Set(SIDES.flatMap((s) => sheets?.[s].starters.map((p) => p.player_id) ?? []));
  const ghosts = new Map(SIDES.flatMap((s) => (sheets ? [...paperSlots(sheets[s])] : [])));
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
        <VizBox state={pos}>{(d) => <AveragePositions data={d} squads={squads} teamNames={names} starters={starters} ghosts={ghosts} />}</VizBox>
      </div>
    </section>
  );
}
