// The fan's match phases (C20, #391): who was on top when, as one band of 15-minute blocks in the kit
// colours and one sentence, no numbers. "On top" is the API's field tilt for the block (the share of
// the touches in the final third): a clear lead colours the block, a close one stays grey.
import type { CSSProperties } from "react";
import { isNum, reached, useAnalysis, type Phase, type Side } from "../../data/analysis";
import { useMatch } from "../../data/match";
import { useT } from "../../i18n";

/** Field tilt this far either side of 50% counts as being on top. */
const CLEAR = 8;

/** Who was on top in each block: a side, "even", or "todo" for a block not reached. */
export function onTop(p: Phase): Side | "even" | "todo" {
  if (!reached(p)) return "todo";
  const h = p.home.field_tilt_pct;
  if (!isNum(h)) return "even";
  return h >= 50 + CLEAR ? "home" : h <= 50 - CLEAR ? "away" : "even";
}

/** The longest run of blocks one side was on top: the spell the sentence names. */
export function longestSpell(phases: readonly Phase[]): { side: Side; from: number; to: number } | null {
  type Run = { side: Side; from: number; to: number; n: number };
  const runs: Run[] = [];
  phases.forEach((p, i) => {
    const who = onTop(p);
    if (who !== "home" && who !== "away") return;
    const last = runs.at(-1);
    if (last && last.side === who && onTop(phases[i - 1]) === who) Object.assign(last, { to: p.to, n: last.n + 1 });
    else runs.push({ side: who, from: p.from, to: p.to, n: 1 });
  });
  const best = runs.reduce<Run | null>((b, r) => (!b || r.n > b.n ? r : b), null);
  return best && { side: best.side, from: best.from, to: best.to };
}

export default function FanPhases({ upTo }: { upTo: number | null }) {
  const { match, teams } = useMatch();
  const t = useT();
  const { data } = useAnalysis(match.match_id, upTo);
  const phases = data?.phases ?? [];
  if (!phases.some(reached)) return null;
  const spell = longestSpell(phases);
  const live = upTo !== null;
  return (
    <section className="live-sec" aria-labelledby="fan-phases-hd">
      <header className="live-hd">
        <h2 id="fan-phases-hd">{t("rp.fan.title")}</h2>
        <p className="muted">{t("rp.fan.note")}</p>
      </header>
      <div className="card rp-fan">
        <p className="rp-take">
          {spell ? t(live ? "rp.fan.takeLive" : "rp.fan.take", { team: teams[spell.side].name, from: spell.from, to: spell.to }) : t(live ? "rp.fan.evenLive" : "rp.fan.even")}
        </p>
        <ol className="rp-band" aria-label={t("rp.fan.title")}>
          {phases.map((p, i) => {
            const who = onTop(p);
            const label = who === "todo" ? t("rp.ph.notStarted") : who === "even" ? t("rp.fan.evenBlock") : t("rp.fan.onTop", { team: teams[who].short_name });
            return (
              <li key={p.from} className={`b-${who}`} style={{ "--c": who === "home" || who === "away" ? `var(--pv-${who})` : undefined } as CSSProperties}>
                <span className="rp-band-k">{`${p.from}′–${p.to}′${i === phases.length - 1 || p.to === 45 ? "+" : ""}`}</span>
                <span className="rp-band-v">{label}</span>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
