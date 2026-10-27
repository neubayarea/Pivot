// The match pictures on the live tab (C11, components from Bx12 #287): one at a time, picked
// with a switch, following the replay or the live clock. The heatmap and the pass network show
// one team, the ♥ team first when the viewer picked one.
import { useState } from "react";
import type { Side } from "../data/match";
import { useMatch } from "../data/match";
import { usePrefs } from "../i18n";
import Segmented from "./Segmented";
import { AveragePositions, Heatmap, PassNetwork, ShotMap, VizBox, useAveragePositions, useHeatmaps, usePassNetwork, useShotMap } from "./viz";

type Pic = "shots" | "heat" | "net" | "pos";

export default function MatchPictures({ upTo }: { upTo: number | null }) {
  const { match, teams, squads } = useMatch();
  const { prefs, t } = usePrefs();
  const [pic, setPic] = useState<Pic>("shots");
  const [side, setSide] = useState<Side>(prefs.focus_team ?? "home");
  const [shot, setShot] = useState<string | null>(null);
  const id = match.match_id;
  const opts = { upTo, stepS: 60 };
  // Only the picture on screen is fetched.
  const shots = useShotMap(pic === "shots" ? id : null, opts);
  const heat = useHeatmaps(pic === "heat" ? id : null, opts);
  const net = usePassNetwork(pic === "net" ? id : null, opts);
  const pos = useAveragePositions(pic === "pos" ? id : null, opts);
  const names = { home: teams.home.name, away: teams.away.name };
  const focus = prefs.focus_player_id;

  return (
    <div className="pics">
      <div className="pics-ctl">
        <Segmented label={t("pics.pick")} value={pic} onChange={setPic} options={[
          { value: "shots", label: t("viz.shots.title") },
          { value: "heat", label: t("viz.heat.title") },
          { value: "net", label: t("viz.net.title") },
          // C12: average positions are an analyst's picture.
          ...(prefs.audience === "fan" ? [] : [{ value: "pos" as const, label: t("viz.pos.title") }]),
        ]} />
        {(pic === "heat" || pic === "net") && (
          <Segmented label={t("pics.side")} value={side} onChange={setSide} options={[
            { value: "home", label: teams.home.name },
            { value: "away", label: teams.away.name },
          ]} />
        )}
      </div>
      <div className="pics-bd">
        {pic === "shots" && (
          <VizBox state={shots}>
            {(d) => <ShotMap data={d} squads={squads} teamNames={names} selected={shot} onPick={(e) => setShot(e === shot ? null : e)} />}
          </VizBox>
        )}
        {pic === "heat" && <VizBox state={heat}>{(d) => <Heatmap data={d} side={side} playerId={focus} squads={squads} teamNames={names} />}</VizBox>}
        {pic === "net" && <VizBox state={net}>{(d) => <PassNetwork data={d} side={side} squads={squads} teamNames={names} focus={focus} />}</VizBox>}
        {pic === "pos" && <VizBox state={pos}>{(d) => <AveragePositions data={d} squads={squads} teamNames={names} focus={focus} />}</VizBox>}
      </div>
    </div>
  );
}
