import { useConnection, useMaybeMatch } from "../data/match";
import Button from "./Button";

/** The cream strip under the top bar while the live feed is down ("05 S1" states). The board keeps the last data. */
export default function ConnectionBanner() {
  const conn = useConnection();
  const view = useMaybeMatch();
  // Before the first load StartupScreen says what is wrong in full.
  if (!conn || !view || (conn.state !== "reconnecting" && conn.state !== "failed")) return null;
  const paused = <span className="at">Data paused at {view.match.clockLabel}</span>;

  if (conn.state === "failed") {
    return (
      <div className="banner warn" role="alert">
        Live feed unavailable: {conn.reason}.
        <span className="sp" />
        {paused}
      </div>
    );
  }
  return (
    <div className="banner warn" role="status" aria-live="polite">
      Live connection lost. Reconnecting… (attempt {conn.attempt})
      <Button onClick={conn.retryNow}>Retry now</Button>
      <span className="sp" />
      {paused}
    </div>
  );
}
