// The match pictures on the live tab (C11, components from Bx12 #287): one at a time, picked
// with a switch, following the replay or the live clock. The heatmap and the pass network show
// one team, the ♥ team first when the viewer picked one.
import { useState } from "react";
import type { Side } from "../data/match";
import { useMatch } from "../data/match";
import { roleGroup } from "../data/persona";
import { usePrefs } from "../i18n";
import FollowButton from "./FollowButton";
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
  // C13: a name picked here shows that player's heatmap or passes, with a Follow button;
  // the followed player is picked to start with when they play for the side shown.
  const [picked, setPicked] = useState<string | null>(null);
  const roster = squads[side];
  const who = picked && roster.some((p) => p.player_id === picked) ? picked
    : roster.some((p) => p.player_id === focus) ? focus : null;
  const whoName = who ? roster.find((p) => p.player_id === who)?.name ?? "" : "";
  const fan = prefs.audience === "fan";
  const pickable = (pic === "heat" || pic === "net") && roster.length > 0;
  // The pass network's own count per player (the same report the picture draws), beside each name.
  const nodes = pic === "net" ? net.data?.teams[side]?.nodes : undefined;
  const count = nodes ? { of: new Map(nodes.map((n) => [n.player_id, n.passes])), total: nodes.reduce((a, n) => a + n.passes, 0) } : null;

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
      </div>
      {/* C17 (#367): the chart takes two thirds and the picker sits beside it, sticky under the match
          header, so a fan can switch player without scrolling away from the pitch (FotMob / Sofascore). */}
      <div className={`pics-row${pickable ? " with-side" : ""}`}>
        <div className="pics-bd">
          {pic === "shots" && (
            <VizBox state={shots}>
              {(d) => <ShotMap data={d} squads={squads} teamNames={names} selected={shot} onPick={(e) => setShot(e === shot ? null : e)} />}
            </VizBox>
          )}
          {pic === "heat" && <VizBox state={heat}>{(d) => <Heatmap data={d} side={side} playerId={who} squads={squads} teamNames={names} />}</VizBox>}
          {pic === "net" && <VizBox state={net}>{(d) => <PassNetwork data={d} side={side} squads={squads} teamNames={names} focus={who ?? focus} />}</VizBox>}
          {pic === "pos" && <VizBox state={pos}>{(d) => <AveragePositions data={d} squads={squads} teamNames={names} focus={focus} />}</VizBox>}
        </div>
        {pickable && (
          <aside className="pics-side">
            <Segmented label={t("pics.side")} value={side} onChange={setSide} options={[
              { value: "home", label: teams.home.name },
              { value: "away", label: teams.away.name },
            ]} />
            <ol className="pics-list" aria-label={t("pics.player")}>
              <li>
                <button type="button" aria-pressed={who === null} onClick={() => setPicked(null)}>
                  <span className="pl-name">{t("pics.wholeTeam")}</span>
                  {count && <span className="pl-n num">{count.total}</span>}
                </button>
              </li>
              {roster.map((p) => (
                <li key={p.player_id}>
                  <button type="button" aria-pressed={who === p.player_id} onClick={() => setPicked(p.player_id)}>
                    <span className="pl-shirt num">{p.shirt ?? ""}</span>
                    <span className="pl-name">{p.name}</span>
                    <span className="pl-pos">{p.role ? (fan ? t(`role.${roleGroup(p.role)}`) : p.role) : ""}</span>
                    {count && <span className="pl-n num">{count.of.get(p.player_id) ?? 0}</span>}
                  </button>
                </li>
              ))}
            </ol>
            {count && <p className="pics-count muted">{t("pics.countPasses")}</p>}
            {who && <FollowButton playerId={who} name={whoName} />}
          </aside>
        )}
      </div>
    </div>
  );
}
