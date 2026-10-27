// The starting line-ups and formations (Ax59), Premier League style: both XIs on one pitch, home
// attacking up from the bottom, away down from the top, then each team's list with its bench.
// Places come from the formation's rows, or the team sheet's anchors when the rows do not add up;
// the fixture has no sheets and gets the squad lists only.
// C11 (Ax63): each team in its kit colour from the page's tokens, so the night theme lightens it too.
import type { TeamSheet } from "@pivot/contracts";
import { useMatch, type Side, type SquadPlayer } from "../data/match";
import { useT } from "../i18n";
import { surname } from "./FocusPickers";
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

function FormationPitch({ sheets }: { sheets: Record<Side, TeamSheet> }) {
  const { teams, squads } = useMatch();
  const t = useT();
  const byId = new Map([...squads.home, ...squads.away].map((p) => [p.player_id, p]));
  const places = { home: formationPlaces("home", sheets.home), away: formationPlaces("away", sheets.away) };
  return (
    <svg className="lu-pitch" viewBox={`-2 -2 ${W + 4} ${H + 8}`} role="img"
      aria-label={t("pre.pitchLabel", { home: `${teams.home.name} ${sheets.home.formation}`, away: `${teams.away.name} ${sheets.away.formation}` })}>
      <rect x="0" y="0" width={W} height={H} className="lu-grass" />
      <line x1="0" x2={W} y1={H / 2} y2={H / 2} className="lu-line" />
      <circle cx={W / 2} cy={H / 2} r="9.15" className="lu-line" fill="none" />
      <rect x={W / 2 - 20.16} y="0" width="40.32" height="16.5" className="lu-line" fill="none" />
      <rect x={W / 2 - 20.16} y={H - 16.5} width="40.32" height="16.5" className="lu-line" fill="none" />
      {(["home", "away"] as Side[]).map((side) => (
        <g key={side} className={`lu-team ${side}`}>
          {sheets[side].starters.map((s) => {
            const [cx, cy] = places[side]?.get(s.player_id) ?? place(side, s.anchor);
            const p = byId.get(s.player_id);
            return (
              <g key={s.player_id} transform={`translate(${cx} ${cy})`}>
                <circle r="3.1" />
                <text className="lu-no" dy="1.1">{p?.shirt ?? ""}</text>
                <text className="lu-nm" dy="6.4">{surname(p?.name ?? s.player_id)}</text>
              </g>
            );
          })}
        </g>
      ))}
    </svg>
  );
}

function TeamList({ side, sheet }: { side: Side; sheet?: TeamSheet }) {
  const { teams, squads } = useMatch();
  const t = useT();
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
        <span><i className={`pre-kit ${side}`} aria-hidden="true" />{teams[side].name}</span>
        {sheet && <small>{sheet.formation}</small>}
      </h3>
      <ol aria-label={sheet ? t("pre.starters") : t("pre.squad")}>
        {starters.map((p) => (
          <li key={p.player_id}>
            <span className="no num">{p.shirt ?? ""}</span>
            <span className="nm">{p.name}{sheet?.captain_id === p.player_id && <abbr title={t("pre.captain")}> (C)</abbr>}</span>
            <span className="rl">{p.slotRole ?? p.role ?? ""}</span>
          </li>
        ))}
      </ol>
      {bench.length > 0 && (
        <>
          <h4>{t("pre.bench")}</h4>
          <ul className="lu-bench">
            {bench.map((p) => (
              <li key={p.player_id}><span className="no num">{p.shirt ?? ""}</span> {p.name}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export default function Lineups() {
  const { sheets } = useMatch();
  return (
    <div className={`lineups${sheets ? "" : " no-sheet"}`}>
      {sheets && <FormationPitch sheets={sheets} />}
      <TeamList side="home" sheet={sheets?.home} />
      <TeamList side="away" sheet={sheets?.away} />
    </div>
  );
}
