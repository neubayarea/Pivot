import { useState } from "react";
import { startDemo } from "../data/demo";
import Button from "./Button";

/** The primary button that gets a match going when none is in progress. */
export default function StartDemoButton({ matchId, children = "Start demo match" }: { matchId?: string; children?: string }) {
  const [busy, setBusy] = useState(false);
  return (
    <Button variant="primary" disabled={busy} onClick={() => { setBusy(true); void startDemo(matchId); }}>
      {busy ? "Starting…" : children}
    </Button>
  );
}
