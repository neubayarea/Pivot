// Ax92 (#435): the followed ★ player's match at the top of the overview: a 0–90+ strip with a mark
// for each goal, shot, key pass, card and substitution of his, and the same as a list. Each one opens
// the Replay tab a little before it. Renders nothing with no ★ player.
import type { CSSProperties } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { Pivot1 as Pivot } from "@pivot/contracts";
import { useMatch } from "../data/match";
import { involvedIn, INVOLVED_WINDOW_MIN, playerMoments, type PlayerMoment } from "../data/follow";
import { usePersona } from "../data/persona";
import { tabSearch } from "../data/tab";
import { useT, type MessageKey } from "../i18n";
import { surname } from "./Pitch";

/** Seconds of lead-in before the moment when the replay opens on it. */
const LEAD_S = 60;

export default function PlayerMatch() {
  const { match, events, playerName, playback } = useMatch();
  const { player } = usePersona();
  const t = useT();
  const navigate = useNavigate();
  const { search } = useLocation();
  if (!player) return null;
  const name = playerName(player);
  const moments = playerMoments(events, player);
  const end = Math.max(90 * 60, match.clock, ...events.map((e) => e.t));
  const open = (m: PlayerMoment) => {
    const at = Math.max(0, m.event.t - LEAD_S);
    if (playback) {
      playback.setPlaying(false);
      playback.seek(at);
      navigate({ search: tabSearch(search, "replay") });
    } else {
      const q = new URLSearchParams(tabSearch(search, "replay"));
      q.set("from", String(Math.floor(at / 60)));
      window.location.assign(`/?${q}`);
    }
    window.scrollTo({ top: 0 });
  };
  const what = (m: PlayerMoment) => t(`pm.${m.kind}` as MessageKey, { name: m.other ? playerName(m.other) : "" });
  const minute = (m: PlayerMoment) => m.event.clock_label.replace(/'/g, "′");
  return (
    <section className="pm" aria-labelledby="pm-hd">
      <header>
        <h2 id="pm-hd">{t("pm.title", { name })}</h2>
        <p className="muted">{t("pm.note")}</p>
      </header>
      <div className="pm-strip" aria-hidden="true">
        <span className="pm-axis" />
        {[0, 45, 90].map((m) => <span key={m} className="pm-tick num" style={{ left: `${(m * 60 / end) * 100}%` }}>{m}′</span>)}
        {moments.map((m) => (
          <span key={`${m.kind}-${m.event.event_id}`} className={`pm-mk ${m.kind}`} style={{ left: `${(m.event.t / end) * 100}%` } as CSSProperties}
            title={`${minute(m)} ${what(m)}`} />
        ))}
      </div>
      {moments.length ? (
        <ul className="pm-list">
          {moments.map((m) => (
            <li key={`${m.kind}-${m.event.event_id}`}>
              <button type="button" onClick={() => open(m)} aria-label={t("pm.open", { minute: minute(m), what: what(m) })}>
                <b className="num">{minute(m)}</b>
                <span className={`pm-ico ${m.kind}`} aria-hidden="true" />
                <span>{what(m)}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">{t("pm.none", { name: surname(name) })}</p>
      )}
    </section>
  );
}

/** "Sahaltessen involved" / "not involved" on a turning point, with the rule in its tooltip; nothing with no ★ player. */
export function InvolvedTag({ pivot }: { pivot: Pivot }) {
  const { events, eventById, playerName } = useMatch();
  const { player } = usePersona();
  const t = useT();
  if (!player) return null;
  const name = surname(playerName(player));
  const yes = involvedIn(pivot, player, events, eventById);
  return (
    <span className={`inv-tag${yes ? " yes" : ""}`} title={t("inv.rule", { name, n: INVOLVED_WINDOW_MIN })}>
      {t(yes ? "inv.yes" : "inv.no", { name })}
    </span>
  );
}
