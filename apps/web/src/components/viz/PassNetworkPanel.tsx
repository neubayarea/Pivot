// The pass network with its controls (C21, #401). An analyst picks the whole match or one half and
// the fewest passes for a line (the API's `period` and `min_passes`); a fan gets the whole match
// without controls. The picture is PassNetwork's.
import { useState } from "react";
import type { Side, SquadPlayer } from "../../data/view";
import { usePassNetwork } from "../../data/viz";
import { usePrefs } from "../../i18n";
import Segmented from "../Segmented";
import PassNetwork from "./PassNetwork";
import { VizBox } from "./index";

export const MIN_LINE = 1;
export const MAX_LINE = 10;
export const DEFAULT_LINE = 3;                  // the API's own default (pictures.MIN_PASSES)

type Half = "all" | "1" | "2";

export default function PassNetworkPanel({ matchId, upTo, side, squads, teamNames, focus = null }: {
  matchId: string | null; upTo: number | null; side: Side;
  squads?: Record<Side, SquadPlayer[]>; teamNames?: Record<Side, string>; focus?: string | null;
}) {
  const { prefs, t } = usePrefs();
  const fan = prefs.audience === "fan";
  const [half, setHalf] = useState<Half>("all");
  const [min, setMin] = useState(DEFAULT_LINE);
  const period = fan || half === "all" ? null : (Number(half) as 1 | 2);
  const net = usePassNetwork(matchId, { upTo, stepS: 60, period, minPasses: fan ? undefined : min });
  return (
    <div className="viz-net-panel">
      {!fan && (
        <div className="viz-net-ctl">
          <Segmented label={t("viz.net.halfLabel")} value={half} onChange={setHalf} options={[
            { value: "all", label: t("viz.net.half.all") },
            { value: "1", label: t("viz.net.half.1") },
            { value: "2", label: t("viz.net.half.2") },
          ]} />
          <label className="viz-net-min">
            <span>{t("viz.net.min", { n: min })}</span>
            <input type="range" min={MIN_LINE} max={MAX_LINE} step={1} value={min} aria-valuetext={t("viz.net.min", { n: min })}
              onChange={(e) => setMin(Number(e.target.value))} />
          </label>
        </div>
      )}
      <VizBox state={net}>{(d) => <PassNetwork data={d} side={side} squads={squads} teamNames={teamNames} focus={focus} />}</VizBox>
    </div>
  );
}
