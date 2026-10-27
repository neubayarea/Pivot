// The match select in the top bar (Ax6). Picking one reloads S1 with that match and remembers it.
import type { Match } from "@pivot/contracts";
import { matchLabel, useMatchChoice, useMatchList, type MatchList } from "../data/choice";
import { useMatch } from "../data/match";
import { useT } from "../i18n";

type ViewProps = MatchList & { value: string; onChange: (id: string) => void };

export function MatchPickerView({ matches, sims, value, onChange }: ViewProps) {
  const t = useT();
  // The shown match may not be in the list yet (first poll still running). The API lists the
  // simulated matches in seed-list order, the default (first) one on top (Ax55), so keep its order.
  const shown = matches.some((m) => m.match_id === value) ? matches : [];
  return (
    <span className="match-pick">
      <select aria-label={t("picker.label")} value={value} onChange={(e) => onChange(e.target.value)}>
        {shown.length === 0 && <option value={value}>{value}</option>}
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
  const { match } = useMatch();
  const list = useMatchList(choice !== null);
  if (!choice) return null;
  return <MatchPickerView {...list} value={match.match_id} onChange={choice.choose} />;
}
