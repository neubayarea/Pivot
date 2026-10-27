// 赛前 · Pre-match (Ax59): who starts and in what shape, from the match payload, then the build-up
// (Ax60): form, table, head-to-head, news and each coach's plan. The fixture has no pre-match data,
// so it shows the line-ups only.
import Lineups from "../../components/Lineups";
import PreMatch from "../../components/PreMatch";
import TeamTactics from "../../components/TeamTactics";
import { useMatch } from "../../data/match";
import { useT } from "../../i18n";

export function PreMatchTab() {
  const t = useT();
  const { preMatch } = useMatch();
  return (
    <>
      <section className="post-sec" aria-labelledby="pre-lineups-hd">
        <header className="sec-hd">
          <h2 id="pre-lineups-hd">{t("pre.lineups")}</h2>
          <p className="muted">{t("pre.lineupsNote")}</p>
        </header>
        <Lineups />
      </section>
      {preMatch && (
        <section className="post-sec pre-slot" data-slot="prematch" aria-labelledby="pre-buildup-hd">
          <header className="sec-hd">
            <h2 id="pre-buildup-hd">{t("pre.buildUp")}</h2>
            <p className="muted">{t("pre.buildUpNote")}</p>
          </header>
          <PreMatch />
          <TeamTactics />
        </section>
      )}
    </>
  );
}
