// 赛前 · Preview (C13 #316): the build-up without the line-ups, which have their own tab now:
// form, table and head-to-head first, then the news, ties and context effects (Carry3's pieces).
// #315: the form in detail (home and away, the last five with half-time scores, the next match and
// who rests) follows the build-up, from its own endpoint; it is left out until that answers.
// #311: the blocks follow `ORDER[audience].pre`: fans read the storylines first, analysts the
// numbers first. The ids this tab has no block for (your team, spotlight, and the plan and
// line-ups, which live on the line-ups tab) are skipped.
import { Fragment, type ReactNode } from "react";
import { PreMatchStories, PreMatchTop } from "../../components/PreMatch";
import PreMatchDeep from "../../components/PreMatchDeep";
import StartDemoButton from "../../components/StartDemoButton";
import { useMatch } from "../../data/match";
import { usePersona } from "../../data/persona";
import { useT } from "../../i18n";

export function PreviewTab() {
  const t = useT();
  const { preMatch, match } = useMatch();
  const { order } = usePersona();
  // Before kick-off this is the tab the match opens on, so it is where the match is started.
  const start = match.status === "scheduled" && (
    <div className="live-start">
      <p className="muted">{t("board.kickoffPending")}</p>
      <StartDemoButton matchId={match.match_id}>{t("demo.startMatch")}</StartDemoButton>
    </div>
  );
  if (!preMatch) return <>{start}<p className="muted">{t("tabs.previewNone")}</p><PreMatchDeep /></>;
  // Form and head-to-head are one build-up section, so "form" places it whole, the detail after it.
  const blocks: Partial<Record<(typeof order.pre)[number], ReactNode>> = {
    form: (
      <>
        <section className="post-sec pre-slot" data-slot="prematch" aria-labelledby="pre-buildup-hd">
          <header className="sec-hd">
            <h2 id="pre-buildup-hd">{t("pre.buildUp")}</h2>
            <p className="muted">{t("pre.buildUpNote")}</p>
          </header>
          <PreMatchTop />
        </section>
        <PreMatchDeep />
      </>
    ),
    stories: <PreMatchStories />,
  };
  return (
    <>
      {start}
      {order.pre.map((id) => blocks[id] && <Fragment key={id}>{blocks[id]}</Fragment>)}
    </>
  );
}
