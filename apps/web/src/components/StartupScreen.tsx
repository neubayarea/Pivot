import { REPLAY_URL } from "../data/demo";
import { useConnection, type Connection } from "../data/match";
import { useT } from "../i18n";
import Button from "./Button";
import Skeleton from "./Skeleton";
import StartDemoButton from "./StartDemoButton";
import StateCard from "./StateCard";


/** S1 before the live feed has a match: card outlines while loading, else what went wrong and what to do. */
export default function StartupScreen() {
  const conn = useConnection();
  return conn ? <Startup conn={conn} /> : <Skeleton />;
}

export function Startup({ conn }: { conn: Connection }) {
  const { problem } = conn;
  const t = useT();
  const replay = (
    <a className="btn" href={REPLAY_URL}>
      {t("startup.replay")}
    </a>
  );
  if (problem?.kind === "no-matches") {
    return (
      <StateCard title={t("startup.noMatches.title")} actions={<StartDemoButton />}>
        <p>{t("startup.noMatches.body")}</p>
      </StateCard>
    );
  }
  if (problem?.kind === "not-found") {
    return (
      <StateCard title={t("startup.notFound.title")} tone="error" actions={<>
        <a className="btn pri" href="/">{t("startup.notFound.latest")}</a>
        {replay}
      </>}>
        <p>{t("startup.notFound.body", { id: problem.matchId })}</p>
      </StateCard>
    );
  }
  if (conn.state === "failed") {
    return (
      <StateCard title={t("startup.failed.title")} tone="error" actions={<>
        <Button variant="primary" onClick={() => window.location.reload()}>{t("common.reload")}</Button>
        {replay}
      </>}>
        <p>{conn.reason ?? t("startup.failed.reason")}.</p>
      </StateCard>
    );
  }
  if (problem) {
    const retry = <Button variant="primary" onClick={conn.retryNow}>{t("common.retryNow")}</Button>;
    const trying = conn.attempt > 0 && <p className="muted">{t("startup.trying", { n: conn.attempt })}</p>;
    return problem.kind === "server" ? (
      <StateCard title={t("startup.server.title")} tone="error" actions={<>{retry}{replay}</>}>
        <p>{t("startup.server.body", { status: problem.status })}</p>
        {trying}
      </StateCard>
    ) : (
      <StateCard title={t("startup.unreachable.title")} tone="error" actions={<>{retry}{replay}</>}>
        <p>{t("startup.unreachable.body")}</p>
        {trying}
      </StateCard>
    );
  }
  return <Skeleton />;
}
