// 赛前 · Preview (C13 #316): the build-up without the line-ups, which have their own tab now:
// form, table and head-to-head first, then the news, ties and context effects (Carry3's pieces).
import { PreMatchStories, PreMatchTop } from "../../components/PreMatch";
import StartDemoButton from "../../components/StartDemoButton";
import { useMatch } from "../../data/match";
import { useT } from "../../i18n";

export function PreviewTab() {
  const t = useT();
  const { preMatch, match } = useMatch();
  // Before kick-off this is the tab the match opens on, so it is where the match is started.
  const start = match.status === "scheduled" && (
    <div className="live-start">
      <p className="muted">{t("board.kickoffPending")}</p>
      <StartDemoButton matchId={match.match_id}>{t("demo.startMatch")}</StartDemoButton>
    </div>
  );
  if (!preMatch) return <>{start}<p className="muted">{t("tabs.previewNone")}</p></>;
  return (
    <>
      {start}
      <section className="post-sec pre-slot" data-slot="prematch" aria-labelledby="pre-buildup-hd">
        <header className="sec-hd">
          <h2 id="pre-buildup-hd">{t("pre.buildUp")}</h2>
          <p className="muted">{t("pre.buildUpNote")}</p>
        </header>
        <PreMatchTop />
      </section>
      <PreMatchStories />
    </>
  );
}
