import { useState } from "react";
import { startDemo } from "../data/demo";
import { useT } from "../i18n";
import Button from "./Button";

/** The primary button that gets a match going when none is in progress. */
export default function StartDemoButton({ matchId, children }: { matchId?: string; children?: string }) {
  const [busy, setBusy] = useState(false);
  const t = useT();
  return (
    <Button variant="primary" disabled={busy} onClick={() => { setBusy(true); void startDemo(matchId); }}>
      {busy ? t("demo.starting") : (children ?? t("demo.start"))}
    </Button>
  );
}
