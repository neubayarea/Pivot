import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import type { ViewerPrefs } from "@pivot/contracts";
import Segmented from "../components/Segmented";
import Stamp from "../components/Stamp";
import StateCard from "../components/StateCard";
import { byMatchday, liveNow, useHub, useNow, type HubLine, type HubLive, type HubTeam } from "../data/hub";
import { liveHref } from "../data/liveClock";
import { usePrefs, useT } from "../i18n";
import "../styles/hub.css";

// The home page (C14, #354): a match centre like FotMob's, Sofascore's or the Premier League
// site's. The simulated live match on top (its clock tied to the wall clock, data/liveClock.ts),
// then every stored match by matchday. A match opens on its own page (`/?match=…`); the six tabs
// there are unchanged. The viewer's team is marked; fan or analyst changes what each line says.

/** The hub is `/` with no match in the link; `?match=` still opens the match page (App.tsx, not in the fixture replay). */
export function isHubPage(pathname: string, search: string): boolean {
  return pathname === "/" && !new URLSearchParams(search).has("match");
}

const LANGUAGES = [
  { value: "en", label: "EN" },
  { value: "zh", label: "中文", lang: "zh" },
  { value: "es", label: "ES" },
] as const;

type Side = "home" | "away";
const kit = (team: HubTeam) => ({ "--kit": team.color }) as CSSProperties;

function HubBar({ prefs, onPrefsChange, teams }: {
  prefs: ViewerPrefs; onPrefsChange: (p: ViewerPrefs) => void; teams: { home: HubTeam; away: HubTeam } | null;
}) {
  const t = useT();
  return (
    <header className="top">
      <Link to="/" className="brand">Pivot</Link>
      <span className="sp" />
      <Segmented
        label={t("top.audience")}
        options={[{ value: "fan", label: t("top.audience.fan") }, { value: "analyst", label: t("top.audience.analyst") }]}
        value={prefs.audience}
        onChange={(audience) => onPrefsChange({ ...prefs, audience })}
      />
      {teams && (
        <Segmented
          label={t("top.team.label")}
          options={[
            { value: "none", label: t("top.team.none") },
            { value: "home", label: teams.home.short_name },
            { value: "away", label: teams.away.short_name },
          ]}
          value={prefs.focus_team ?? "none"}
          onChange={(v) => onPrefsChange({ ...prefs, focus_team: v === "none" ? null : v, focus_player_id: null })}
        />
      )}
      <Segmented
        label={t("top.language")}
        options={LANGUAGES}
        value={prefs.language}
        onChange={(language) => onPrefsChange({ ...prefs, language })}
      />
    </header>
  );
}

function LiveNow({ live, line, fav }: { live: HubLive; line: HubLine; fav: string | null }) {
  const t = useT();
  const now = liveNow(live, useNow());
  const href = liveHref(live.match_id);
  const left = Math.max(1, Math.ceil((live.length_s + 120 - now.clock) / 60));
  return (
    <section className="hub-live" aria-labelledby="hub-live-h">
      <div className="hub-live-head">
        <h2 id="hub-live-h">{t("hub.live.title")}</h2>
        <Stamp tone="live">{t("hub.live.sim")}</Stamp>
        <span className="hub-live-min num" aria-label={t("hub.live.clock", { minute: now.minute })}>
          {now.over ? t("status.finished") : `${now.minute}′`}
        </span>
      </div>
      <Link to={href} className="hub-live-score" aria-label={t("hub.open", {
        home: line.home.name, away: line.away.name, score: `${now.score.home}–${now.score.away}` })}>
        <TeamName team={line.home} fav={fav} />
        <span className="hub-live-goals num">{now.score.home}–{now.score.away}</span>
        <TeamName team={line.away} fav={fav} />
      </Link>
      <div className="hub-live-foot">
        <p>
          {now.over
            ? t("hub.live.break", { n: left })
            : now.lastPivot === null ? t("hub.live.noPivot") : t("hub.live.pivot", { minute: now.lastPivot + 1 })}
        </p>
        <Link to={href} className="btn pri">{t("hub.live.watch")}</Link>
      </div>
      <p className="hub-note">{t("hub.live.note")}</p>
    </section>
  );
}

function TeamName({ team, fav }: { team: HubTeam; fav: string | null }) {
  const t = useT();
  const mine = fav === team.short_name;
  return (
    <span className={`hub-team${mine ? " mine" : ""}`} style={kit(team)}>
      <span className="hub-dot" aria-hidden="true" />
      {team.name}
      {mine && <span className="sr-only"> ({t("hub.yours")})</span>}
    </span>
  );
}

function verdict(line: HubLine, side: Side): "win" | "draw" | "loss" | null {
  if (line.status !== "finished") return null;
  const us = line.score[side], them = line.score[side === "home" ? "away" : "home"];
  return us > them ? "win" : us < them ? "loss" : "draw";
}

function ResultRow({ line, fav, fan }: { line: HubLine; fav: string | null; fan: boolean }) {
  const t = useT();
  const score = `${line.score.home}–${line.score.away}`;
  const you = fav && (line.home.short_name === fav || line.away.short_name === fav)
    ? verdict(line, line.home.short_name === fav ? "home" : "away") : null;
  return (
    <li>
      <Link to={`/?match=${encodeURIComponent(line.match_id)}&tab=overview`} className="hub-row"
        aria-label={t("hub.open", { home: line.home.name, away: line.away.name, score })}>
        <TeamName team={line.home} fav={fav} />
        <span className="hub-score num">{score}</span>
        <TeamName team={line.away} fav={fav} />
        <span className="hub-meta">{t(fan ? "hub.pivotsFan" : "hub.pivots", { n: line.pivots })}</span>
        <span className="hub-meta">
          {line.best && (fan ? t("hub.bestFan", { name: line.best.name })
            : t("hub.best", { name: line.best.name, rating: line.best.rating.toFixed(1) }))}
        </span>
        <span className="hub-you">{you && t(`hub.you.${you}`)}</span>
      </Link>
    </li>
  );
}

export default function Hub() {
  const { prefs, setPrefs } = usePrefs();
  const t = useT();
  const { data, failed } = useHub();
  const liveLine = data?.matches.find((m) => m.live) ?? null;
  const first = liveLine ?? data?.matches[0] ?? null;
  const teams = first && { home: first.home, away: first.away };
  // The viewer's team is saved as a side of the match they last watched; on the hub it is that club.
  const fav = prefs.focus_team && teams ? teams[prefs.focus_team].short_name : null;
  const results = (data?.matches ?? []).filter((m) => !m.live && m.status === "finished");
  const fan = prefs.audience === "fan";

  return (
    <>
      <HubBar prefs={prefs} onPrefsChange={setPrefs} teams={teams} />
      <main className="page hub">
        <h1>{t("hub.title")}</h1>
        {failed && <StateCard title={t("hub.failed.title")} tone="error">{t("hub.failed")}</StateCard>}
        {!data && !failed && <p className="hub-note" role="status">{t("hub.loading")}</p>}
        {data?.live && liveLine && <LiveNow live={data.live} line={liveLine} fav={fav} />}
        {data && (
          <section className="hub-results" aria-labelledby="hub-results-h">
            <div className="hub-section-head">
              <h2 id="hub-results-h">{t("hub.results.title")}</h2>
              <span className="hub-note">{t("hub.results.note", { n: results.length })}</span>
            </div>
            {data.generating && <p className="hub-note" role="status">{t("hub.generating")}</p>}
            {byMatchday(results).map(([day, lines]) => (
              <div key={day ?? "other"} className="hub-day">
                <h3>{day === null ? t("hub.matchday.none") : t("hub.matchday", { n: day })}</h3>
                <ul>
                  {lines.map((l) => <ResultRow key={l.match_id} line={l} fav={fav} fan={fan} />)}
                </ul>
              </div>
            ))}
          </section>
        )}
      </main>
    </>
  );
}
