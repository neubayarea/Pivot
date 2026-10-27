// 阵容 · Line-ups (C13 #316): both XIs and each coach's plan, taken out of the pre-match tab.
// The pieces are Carry3's (Lineups, TeamTactics); this file only puts them on their own tab.
import Lineups from "../../components/Lineups";
import TeamTactics from "../../components/TeamTactics";
import { useMatch } from "../../data/match";
import { useT } from "../../i18n";

export function LineupsTab() {
  const t = useT();
  const { preMatch } = useMatch();
  return (
    <>
      <section className="post-sec" aria-labelledby="lu-hd">
        <header className="sec-hd">
          <h2 id="lu-hd">{t("pre.lineups")}</h2>
          <p className="muted">{t("pre.lineupsNote")}</p>
        </header>
        <Lineups />
      </section>
      {preMatch && <TeamTactics />}
    </>
  );
}
