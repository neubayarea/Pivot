// 赛前 · Pre-match (Ax59): who starts and in what shape, from the match payload. The form,
// head-to-head and coaches' tactics (PreMatch, TeamTactics) are being built on their own and go
// in the slot below.
import Lineups from "../../components/Lineups";
import { useT } from "../../i18n";

export function PreMatchTab() {
  const t = useT();
  return (
    <>
      <section className="post-sec" aria-labelledby="pre-lineups-hd">
        <header className="sec-hd">
          <h2 id="pre-lineups-hd">{t("pre.lineups")}</h2>
          <p className="muted">{t("pre.lineupsNote")}</p>
        </header>
        <Lineups />
      </section>
      {/* SLOT · <PreMatch /> and <TeamTactics /> (components/PreMatch.tsx, components/TeamTactics.tsx) go here. */}
      <section className="pre-slot" data-slot="prematch" aria-label={t("pre.slot")}>
        <p className="placeholder">{t("pre.slot")}</p>
      </section>
    </>
  );
}
