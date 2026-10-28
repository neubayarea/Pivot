// The starting line-ups and formations (Ax59), Premier League style: both XIs on one pitch, home
// attacking up from the bottom, away down from the top, then each team's list with its bench.
// Places come from the formation's rows, or the team sheet's anchors when the rows do not add up;
// the fixture has no sheets and gets the squad lists only.
// C11 (Ax63): each team in its kit colour from the page's tokens, so the night theme lightens it too.
// Ax69: on the line-ups tab the ♥ team attacks up the page, and each player has the shared ☆ Follow button (#324).
// Once the match is under way each player also shows what he did: goals, cards, when he came on or
// went off, and his rating (data/lineupFacts.ts), in the list and on the pitch.
import { useState, type ReactNode } from "react";
import type { PlayerReport, TeamSheet } from "@pivot/contracts";
import { useClock } from "../data/clock";
import { lineupFacts, shortName, type Facts } from "../data/lineupFacts";
import { useMatch, type Side, type SquadPlayer } from "../data/match";
import { usePlayers } from "../data/persona";
import { usePrefs, useT, type T } from "../i18n";
import FollowButton from "./FollowButton";
import Grass from "./Grass";
import { surname } from "./FocusPickers";
import { TeamKit } from "./PreMatch";
import "../styles/prematch.css";

const W = 68;
const H = 105;
// A team's anchors run from its goal to about the halfway line and a bit; squeezed into its half.
const DEPTH = 0.6;

function place(side: Side, [x, y]: readonly [number, number]): [number, number] {
  const depth = Math.min(H / 2 - 7, x * DEPTH);
  return side === "home" ? [W - y, H - 3 - depth] : [y, 3 + depth];
}

/**
 * Places from the formation, the way match pages draw it: the keeper, then one row per number in
 * "4-2-3-1", slots back to front and left to right. Null when the sheet does not add up, so the
 * anchors are used instead.
 */
function formationPlaces(side: Side, sheet: TeamSheet): Map<string, [number, number]> | null {
  const rows = [1, ...sheet.formation.split("-").map(Number)];
  const slots = sheet.starters.slice().sort((a, b) => a.slot - b.slot);
  if (rows.reduce((n, r) => n + r, 0) !== slots.length) return null;
  const out = new Map<string, [number, number]>();
  const gap = (H / 2 - 9) / (rows.length - 1);
  let i = 0;
  rows.forEach((count, row) => {
    for (let k = 0; k < count; k++, i++) {
      const across = (W * (k + 1)) / (count + 1);           // the team's left to right
      const depth = 4 + row * gap;
      out.set(slots[i].player_id, side === "home" ? [across, H - depth] : [W - across, depth]);
    }
  });
  return out;
}

/** The facts after a name in a list row: goals, cards, the minute of a change, the rating. */
function PlayerFacts({ f, t, at }: { f?: Facts; t: T; at: (s: number) => string }) {
  if (!f) return null;
  return (
    <span className="lu-facts">
      {f.goals > 0 && <span className="lu-goal" role="img" aria-label={t(f.goals === 1 ? "lu.goal" : "lu.goals", { n: f.goals })}>{"⚽".repeat(Math.min(f.goals, 3))}</span>}
      {f.red ? <i className="lu-card red" role="img" aria-label={t("lu.red")} /> : f.yellow && <i className="lu-card yellow" role="img" aria-label={t("lu.yellow")} />}
      {f.on !== undefined && <span className="lu-sub on" aria-label={t("lu.on", { minute: at(f.on) })}><span aria-hidden="true">▲</span> {at(f.on)}′</span>}
      {f.off !== undefined && <span className="lu-sub off" aria-label={t("lu.off", { minute: at(f.off) })}><span aria-hidden="true">▼</span> {at(f.off)}′</span>}
      {f.rating !== undefined && <span className="lu-rating num" aria-label={t("lu.rating", { n: f.rating.toFixed(1) })}>{f.rating.toFixed(1)}</span>}
    </span>
  );
}

/** Goals, cards, changes and ratings so far, or null before kick-off and where they are not wanted. */
function useFacts(on: boolean): Map<string, Facts> | null {
  const { match, events, playback } = useMatch();
  const live = on && match.status !== "scheduled";
  // Whole minutes, like the player card, so a running clock refetches once a minute.
  const upTo = match.status === "finished" && !playback ? null : Math.floor(match.clock / 60) * 60;
  const players = usePlayers(live ? match.match_id : null, upTo);
  return live ? lineupFacts(events, players.data?.players) : null;
}

function FormationPitch({ sheets, up = "home", followed = null, facts, card }: {
  sheets: Record<Side, TeamSheet>; up?: Side; followed?: string | null; facts: Map<string, Facts> | null;
  /** C21 (#401): the card shown while a player is hovered or focused, if any. */
  card?: (playerId: string) => ReactNode;
}) {
  const { teams, squads } = useMatch();
  const t = useT();
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  // Home attacks up the page; with the away side up, the whole pitch turns round.
  const turn = ([x, y]: [number, number]): [number, number] => (up === "home" ? [x, y] : [W - x, H - y]);
  const byId = new Map([...squads.home, ...squads.away].map((p) => [p.player_id, p]));
  const places = { home: formationPlaces("home", sheets.home), away: formationPlaces("away", sheets.away) };
  const svg = (
    <svg className="lu-pitch" viewBox={`-2 -6 ${W + 4} ${H + 12}`} role="img"
      aria-label={t("pre.pitchLabel", { home: `${teams.home.name} ${sheets.home.formation}`, away: `${teams.away.name} ${sheets.away.formation}` })}>
      <Grass w={W} h={H} along="y" />
      <line x1="0" x2={W} y1={H / 2} y2={H / 2} className="lu-line" />
      <circle cx={W / 2} cy={H / 2} r="9.15" className="lu-line" fill="none" />
      <rect x={W / 2 - 20.16} y="0" width="40.32" height="16.5" className="lu-line" fill="none" />
      <rect x={W / 2 - 20.16} y={H - 16.5} width="40.32" height="16.5" className="lu-line" fill="none" />
      {(["home", "away"] as Side[]).map((side) => (
        <g key={side} className={`lu-team ${side}`}>
          {sheets[side].starters.map((s) => {
            const [cx, cy] = turn(places[side]?.get(s.player_id) ?? place(side, s.anchor));
            const p = byId.get(s.player_id);
            const name = surname(p?.name ?? s.player_id);
            const f = facts?.get(s.player_id);
            // The team at the top has its names above the dots, so the two front lines do not meet at halfway.
            const top = side !== up;
            return (
              <g key={s.player_id} className={followed === s.player_id ? "followed" : undefined} transform={`translate(${cx} ${cy})`}
                {...(card ? {
                  tabIndex: 0,
                  onMouseEnter: () => setHover({ id: s.player_id, x: (cx + 2) / (W + 4), y: (cy + 6) / (H + 12) }),
                  onMouseLeave: () => setHover(null),
                  onFocus: () => setHover({ id: s.player_id, x: (cx + 2) / (W + 4), y: (cy + 6) / (H + 12) }),
                  onBlur: () => setHover(null),
                } : {})}>
                <title>{p?.name ?? name}</title>
                <circle r="3.1" />
                <text className="lu-no" dy="1.1">{p?.shirt ?? ""}</text>
                <text className="lu-nm" dy={top ? -4.2 : 6.4}>{shortName(name)}</text>
                {f?.rating !== undefined && <text className="lu-rt" x="3.4" y="-2.2">{f.rating.toFixed(1)}</text>}
                {f && f.goals > 0 && <circle className="lu-ball" cx="-3" cy="-2.6" r="1.1" />}
                {f && (f.red || f.yellow) && <rect className={`lu-cd ${f.red ? "red" : "yellow"}`} x="-4.4" y="0.6" width="1.4" height="2" rx=".2" />}
                {f?.off !== undefined && <text className="lu-offmk" x="3.4" y="3.2">▼</text>}
              </g>
            );
          })}
        </g>
      ))}
    </svg>
  );
  if (!card) return svg;
  const shown = hover && card(hover.id);
  return (
    <div className="lu-pitch-wrap">
      {svg}
      {shown && (
        <div className={`lu-pcard${hover!.x > 0.6 ? " left" : ""}${hover!.y > 0.6 ? " above" : ""}`} role="tooltip"
          style={{ left: `${hover!.x * 100}%`, top: `${hover!.y * 100}%` }}>
          {shown}
        </div>
      )}
    </div>
  );
}

function TeamList({ side, sheet, follow, facts, formation }: { side: Side; sheet?: TeamSheet; follow: boolean; facts: Map<string, Facts> | null; formation: boolean }) {
  const { teams, squads } = useMatch();
  const t = useT();
  const { at } = useClock();
  const byId = new Map(squads[side].map((p) => [p.player_id, p]));
  const starters: (SquadPlayer & { slotRole?: string })[] = sheet
    ? sheet.starters.slice().sort((a, b) => a.slot - b.slot).flatMap((s) => {
      const p = byId.get(s.player_id);
      return p ? [{ ...p, slotRole: s.role }] : [];
    })
    : squads[side];
  const bench = sheet ? sheet.bench.flatMap((id) => byId.get(id) ?? []) : [];
  return (
    <section className={`card lu-list ${side}`}>
      <h3>
        <span><TeamKit side={side} size={48} />{teams[side].name}</span>
        {sheet && formation && <small>{sheet.formation}</small>}
      </h3>
      <ol aria-label={sheet ? t("pre.starters") : t("pre.squad")}>
        {starters.map((p) => (
          <li key={p.player_id}>
            <span className="no num">{p.shirt ?? ""}</span>
            <span className="nm">
              {p.name}{sheet?.captain_id === p.player_id && <abbr title={t("pre.captain")}> (C)</abbr>}
              <PlayerFacts f={facts?.get(p.player_id)} t={t} at={at} />
            </span>
            <span className="rl">{p.slotRole ?? p.role ?? ""}</span>
            {follow && <FollowButton playerId={p.player_id} name={p.name} />}
          </li>
        ))}
      </ol>
      {bench.length > 0 && (
        <>
          <h4>{t("pre.bench")}</h4>
          <ul className="lu-bench">
            {bench.map((p) => (
              <li key={p.player_id}>
                <span className="no num">{p.shirt ?? ""}</span> {p.name}
                <PlayerFacts f={facts?.get(p.player_id)} t={t} at={at} />
                {follow && <FollowButton playerId={p.player_id} name={p.name} />}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

/**
 * `up`: the team attacking up the page (home unless given); `follow`: a ☆ beside every player;
 * `facts`: goals, cards, changes and ratings once the match is under way; `formation`: the shape in
 * each list's header (off where the coach's plan already says it).
 */
export default function Lineups({ up = "home", follow = false, facts: withFacts = false, formation = true, card }: {
  up?: Side; follow?: boolean; facts?: boolean; formation?: boolean;
  /** C21 (#401): a card for a hovered player on the pitch, from his /players/stats row. */
  card?: (p: PlayerReport) => ReactNode;
}) {
  const { sheets, match, playback } = useMatch();
  const { prefs } = usePrefs();
  const facts = useFacts(withFacts);
  const upTo = match.status === "finished" && !playback ? null : Math.floor(match.clock / 60) * 60;
  const rows = usePlayers(card && match.status !== "scheduled" ? match.match_id : null, upTo).data?.players;
  const byId = new Map((rows ?? []).map((p) => [p.player_id, p]));
  const cardOf = card && rows ? (id: string) => (byId.has(id) ? card(byId.get(id)!) : null) : undefined;
  // The team at the bottom of the pitch is listed first.
  const order: Side[] = up === "home" ? ["home", "away"] : ["away", "home"];
  return (
    <div className={`lineups${sheets ? "" : " no-sheet"}${follow ? " with-follow" : ""}`}>
      {sheets && <FormationPitch sheets={sheets} up={up} followed={prefs.focus_player_id} facts={facts} card={cardOf} />}
      {order.map((s) => <TeamList key={s} side={s} sheet={sheets?.[s]} follow={follow} facts={facts} formation={formation} />)}
    </div>
  );
}
