// The match select in the top bar (Ax6). Picking one reloads S1 with that match and remembers it.
import type { Match } from "@pivot/contracts";
import { matchLabel, matchdayOf, useMatchChoice, useMatchList, type MatchList } from "../data/choice";
import { useMatch } from "../data/match";
import { useT } from "../i18n";

type ViewProps = MatchList & { value: string; onChange: (id: string) => void; currentLabel?: string };

export function MatchPickerView({ matches, sims, value, onChange, currentLabel }: ViewProps) {
  const t = useT();
  // The shown match may not be in the list yet (first poll still running). The API lists the
  // simulated matches in seed-list order, the default (first) one on top (Ax55), so keep its order.
  const shown = matches.some((m) => m.match_id === value) ? matches : [];
  return (
    <span className="match-pick">
      <select aria-label={t("picker.label")} value={value} onChange={(e) => onChange(e.target.value)}>
        {/* #354: the open match by its name, never its id, while the list does not have it. */}
        {shown.length === 0 && <option value={value}>{currentLabel ?? value}</option>}
        {shown.map((m: Match) => (
          <option key={m.match_id} value={m.match_id}>
            {matchLabel(m, t)}
          </option>
        ))}
      </select>
      {sims?.generating && (
        <span className="match-gen" role="status">
          {t("picker.generating", { ready: sims.ready, total: sims.total })}
        </span>
      )}
    </span>
  );
}

export default function MatchPicker() {
  const choice = useMatchChoice();
  const { match, playback, teams } = useMatch();
  const t = useT();
  const list = useMatchList(choice !== null);
  if (!choice) return null;
  // C14: the simulated live match shows its score so far, not the final one; the next round's
  // fixtures are on the match centre, not in this list (unless one is open).
  const md = matchdayOf(match.match_id);
  const openLabel = `${teams.home.name} v ${teams.away.name}${md === null ? "" : ` · ${t("picker.matchday", { n: md })}`}`;
  const listed = list.matches.filter((m) => m.status !== "scheduled" || m.match_id === match.match_id);
  const matches = playback?.goLive
    ? listed.map((m) => (m.match_id === match.match_id ? { ...m, score: match.score, status: match.status } : m))
    : listed;
  return <MatchPickerView {...list} matches={matches} value={match.match_id} onChange={choice.choose} currentLabel={openLabel} />;
}
