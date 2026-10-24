import { REPLAY_URL } from "../data/demo";
import { useConnection, type Connection } from "../data/match";
import Button from "./Button";
import Skeleton from "./Skeleton";
import StartDemoButton from "./StartDemoButton";
import StateCard from "./StateCard";

const replay = (
  <a className="btn" href={REPLAY_URL}>
    Watch the demo replay
  </a>
);

/** S1 before the live feed has a match: card outlines while loading, else what went wrong and what to do. */
export default function StartupScreen() {
  const conn = useConnection();
  return conn ? <Startup conn={conn} /> : <Skeleton />;
}

export function Startup({ conn }: { conn: Connection }) {
  const { problem } = conn;
  if (problem?.kind === "no-matches") {
    return (
      <StateCard title="No matches yet" actions={<StartDemoButton />}>
        <p>Start the demo match to see Pivot find the turning points as they happen.</p>
      </StateCard>
    );
  }
  if (problem?.kind === "not-found") {
    return (
      <StateCard title="Match not found" tone="error" actions={<>
        <a className="btn pri" href="/">Open the latest match</a>
        {replay}
      </>}>
        <p>There is no match called “{problem.matchId}”. The link may be from an older demo.</p>
      </StateCard>
    );
  }
  if (conn.state === "failed") {
    return (
      <StateCard title="Live feed unavailable" tone="error" actions={<>
        <Button variant="primary" onClick={() => window.location.reload()}>Reload</Button>
        {replay}
      </>}>
        <p>{conn.reason ?? "The server closed the live connection"}.</p>
      </StateCard>
    );
  }
  if (problem) {
    const retry = <Button variant="primary" onClick={conn.retryNow}>Retry now</Button>;
    const trying = conn.attempt > 0 && <p className="muted">Trying again automatically (attempt {conn.attempt}).</p>;
    return problem.kind === "server" ? (
      <StateCard title="The Pivot server hit a problem" tone="error" actions={<>{retry}{replay}</>}>
        <p>It answered with an error (HTTP {problem.status}). The match data could not be loaded.</p>
        {trying}
      </StateCard>
    ) : (
      <StateCard title="Can’t reach the Pivot server" tone="error" actions={<>{retry}{replay}</>}>
        <p>The live match service is not answering. Check the network, or watch the recorded demo meanwhile.</p>
        {trying}
      </StateCard>
    );
  }
  return <Skeleton />;
}
