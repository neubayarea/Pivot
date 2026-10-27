// The followed player's card (Ax49): what the ★ player picker changes on the page besides the
// explanations. Numbers come from GET /api/matches/{id}/players/stats (#226), up to the clock on
// the board and up to the end of the pivot's window on its detail page. The fixture has no API,
// and a match without tracking frames has no player numbers: the card then stays off.
import { useEffect, useState } from "react";
import type { PlayerMatchStats, PlayerReport } from "@pivot/contracts";
import { Link } from "react-router-dom";
import { useClock } from "../data/clock";
import { api } from "../data/live/api";
import { fixtureMode, useMatch } from "../data/match";
import { type MessageKey, usePrefs } from "../i18n";
import Card from "./Card";
import FollowButton from "./FollowButton";
import { Placeholder } from "./Skeleton";

type Key = "minutes_played" | "rating" | "goals" | "assists" | "shots" | "xg" | "passes" | "key_passes" | "tackles_won"
  | "interceptions" | "duels_won" | "distance_km" | "top_speed_kmh";
type Row = [Key, (v: number, s: PlayerMatchStats) => string];

const pct = (v: number) => `${Math.round(v)}%`;
// Analysts get the full line; fans the numbers they can count themselves, no xG or rating.
const ANALYST: Row[] = [
  ["minutes_played", (v) => `${v}′`], ["rating", (v) => v.toFixed(1)], ["goals", String], ["assists", String],
  ["shots", String], ["xg", (v) => v.toFixed(2)], ["passes", (v, s) => (s.pass_accuracy_pct === null ? String(v) : `${v} · ${pct(s.pass_accuracy_pct)}`)],
  ["key_passes", String], ["tackles_won", String], ["interceptions", String], ["duels_won", String],
  ["distance_km", (v) => v.toFixed(1)],
];
const FAN: Row[] = [
  ["minutes_played", (v) => `${v}′`], ["goals", String], ["assists", String], ["shots", String], ["passes", String],
  ["tackles_won", String], ["distance_km", (v) => v.toFixed(1)], ["top_speed_kmh", (v) => v.toFixed(0)],
];

/** The report for one player up to `upTo` seconds (null: the whole match); undefined while it loads, null when there is none. */
export function usePlayerReport(matchId: string, playerId: string | null, upTo: number | null): PlayerReport | null | undefined {
  const [fixture] = useState(() => typeof window === "undefined" || fixtureMode());
  // Nothing to fetch on the fixture: no report from the start, not a loading flash.
  const [report, setReport] = useState<PlayerReport | null | undefined>(() => (fixture || !playerId ? null : undefined));
  useEffect(() => {
    if (fixture || !playerId) return setReport(null);
    let alive = true;
    api.playerStats(matchId, playerId, upTo).then(
      (r) => alive && setReport(r.players[0] ?? null),
      () => alive && setReport(null),
    );
    return () => {
      alive = false;
    };
  }, [fixture, matchId, playerId, upTo]);
  return fixture || !playerId ? null : report;
}

type Props = {
  /** Elapsed seconds the numbers run to; null for the whole match. */
  upTo: number | null;
  /** The board's moment numbers (①②③) by pivot id; a pivot not in it gets no badge. */
  numbered?: readonly string[];
  /** On the board a moment opens in place; elsewhere it links to its detail page. */
  onPivot?: (pivotId: string) => void;
};

export default function PlayerCard({ upTo, ...rest }: Props) {
  const { match } = useMatch();
  const { prefs } = usePrefs();
  const report = usePlayerReport(match.match_id, prefs.focus_player_id, upTo);
  return report === null ? null : <PlayerCardView report={report} upTo={upTo} {...rest} />;
}

/** The card for a report already fetched (undefined: still loading). */
export function PlayerCardView({ report, upTo, numbered = [], onPivot }: Props & { report: PlayerReport | undefined }) {
  const { match, teams } = useMatch();
  const { t } = usePrefs();
  const { at } = useClock();
  const title = report ? t("player.title", { player: report.name }) : t("player.titleLoading");
  // C13 QA: facts side by side, not a · chain.
  const note = report && `#${report.shirt_number}, ${teams[report.team].short_name}, ${report.role}, 0′–${at(upTo ?? match.clock)}′`;
  return (
    <Card title={title} note={note} className="player-card">
      {report && <FollowButton playerId={report.player_id} name={report.name} />}
      <PlayerNumbers report={report} numbered={numbered} onPivot={onPivot} />
    </Card>
  );
}

/** A report's numbers and the moments the player was in; also the line-ups card's player view (Ax59). */
export function PlayerNumbers({ report, numbered = [], onPivot }: Pick<Props, "numbered" | "onPivot"> & { report: PlayerReport | undefined }) {
  const { prefs, t } = usePrefs();
  const { minute } = useClock();
  const fan = prefs.audience === "fan";
  const label = fan ? "player.fan" : "player";
  return (
    <>
      {report === undefined ? (
        <Placeholder label={t("player.loading")} lines={4} />
      ) : !report.stats ? (
        <p className="muted">{t("player.notOn")}</p>
      ) : (
        <dl className="player-stats">
          {(fan ? FAN : ANALYST).map(([key, fmt]) => (
            <div key={key}>
              <dt>{t(`${label}.${key}` as MessageKey)}</dt>
              <dd>{fmt(report.stats![key], report.stats!)}</dd>
            </div>
          ))}
        </dl>
      )}
      {report && (
        <p className="player-pivots">
          {report.pivots.length ? t("player.inMoments") : t("player.noMoments")}
          {report.pivots.map((p) => {
            const n = numbered.indexOf(p.pivot_id) + 1;
            const text = `${n ? `${n}: ` : ""}${minute(p.minute)}′${p.in_trigger ? `, ${t("player.setOff")}` : ""}`;
            return onPivot ? (
              <button key={p.pivot_id} type="button" className="ev" onClick={() => onPivot(p.pivot_id)}>{text}</button>
            ) : (
              <Link key={p.pivot_id} to={`/pivot/${p.pivot_id}`} className="ev">{text}</Link>
            );
          })}
        </p>
      )}
    </>
  );
}
