// 赛前 · Pre-match (Ax59): who starts and in what shape, from the match payload, then the build-up
// (Ax60): form, table, head-to-head, news and each coach's plan. The fixture has no pre-match data,
// so it shows the line-ups only.
// C11 (Ax63): a match preview's order. The table, form and head-to-head first and biggest, then the
// coach's plan and the line-ups it names, then the news, ties and context effects.
// #315: the form in detail (home and away, the last five with half-time scores, the next match and
// who rests) comes after the build-up, from its own endpoint; it is left out until that answers.
import Lineups from "../../components/Lineups";
import { PreMatchStories, PreMatchTop } from "../../components/PreMatch";
import PreMatchDeep from "../../components/PreMatchDeep";
import TeamTactics from "../../components/TeamTactics";
import { useMatch } from "../../data/match";
import { useT } from "../../i18n";

export function PreMatchTab() {
  const t = useT();
  const { preMatch } = useMatch();
  return (
    <>
      {preMatch && (
        <section className="post-sec pre-slot" data-slot="prematch" aria-labelledby="pre-buildup-hd">
          <header className="sec-hd">
            <h2 id="pre-buildup-hd">{t("pre.buildUp")}</h2>
            <p className="muted">{t("pre.buildUpNote")}</p>
          </header>
          <PreMatchTop />
          <TeamTactics />
        </section>
      )}
      <PreMatchDeep />
      <section className="post-sec" aria-labelledby="pre-lineups-hd">
        <header className="sec-hd">
          <h2 id="pre-lineups-hd">{t("pre.lineups")}</h2>
          <p className="muted">{t("pre.lineupsNote")}</p>
        </header>
        <Lineups />
      </section>
      <PreMatchStories />
    </>
  );
}
