import { useMatchChoice } from "../data/choice";
import { useConnection, useMaybeMatch } from "../data/match";
import { useT } from "../i18n";
import Button from "./Button";

/** The cream strip under the top bar while the live feed is down ("05 S1" states). The board keeps the last data. */
export default function ConnectionBanner() {
  const conn = useConnection();
  const view = useMaybeMatch();
  const t = useT();
  // Before the first load StartupScreen says what is wrong in full.
  if (!conn || !view || (conn.state !== "reconnecting" && conn.state !== "failed")) return null;
  const paused = <span className="at">{t("banner.paused", { clock: view.match.clockLabel })}</span>;

  if (conn.state === "failed") {
    return (
      <div className="banner warn" role="alert">
        {t("banner.failed", { reason: conn.reason ?? t("startup.failed.reason") })}
        <span className="sp" />
        {paused}
      </div>
    );
  }
  return (
    <div className="banner warn" role="status" aria-live="polite">
      {t("banner.reconnecting", { n: conn.attempt })}
      <Button onClick={conn.retryNow}>{t("common.retryNow")}</Button>
      <span className="sp" />
      {paused}
    </div>
  );
}

/** An old link named a match the site no longer has, so the default one is shown (Ax55). */
export function MissingMatchBanner() {
  const choice = useMatchChoice();
  const t = useT();
  if (!choice?.missing) return null;
  return (
    <div className="banner warn" role="status">
      {t("banner.missing", { id: choice.missing })}
      <span className="sp" />
      <Button onClick={choice.dismiss}>{t("banner.dismiss")}</Button>
    </div>
  );
}
