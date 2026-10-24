import { useState } from "react";
import { Route, Routes } from "react-router-dom";
import type { ViewerPrefs } from "@pivot/contracts";
import ConnectionBanner from "./components/ConnectionBanner";
import StartupScreen from "./components/StartupScreen";
import TopBar from "./components/TopBar";
import { MatchProvider } from "./data/match";
import AgentTraces from "./pages/AgentTraces";
import LiveBoard from "./pages/LiveBoard";
import NotFound from "./pages/NotFound";
import PivotDetail from "./pages/PivotDetail";
import WhatIfLab from "./pages/WhatIfLab";

/** Until the live feed has its first state there is no match to put in the top bar: card outlines, or what went wrong. */
const WAITING = (
  <>
    <header className="top">
      <span className="brand">Pivot</span>
    </header>
    <ConnectionBanner />
    <main className="page">
      <StartupScreen />
    </main>
  </>
);

const DEFAULT_PREFS: ViewerPrefs = {
  audience: "analyst",
  language: "en",
  focus_team: null,
  focus_player_id: null,
};

export default function App() {
  const [prefs, setPrefs] = useState<ViewerPrefs>(DEFAULT_PREFS);

  return (
    <MatchProvider fallback={WAITING}>
      <TopBar prefs={prefs} onPrefsChange={setPrefs} />
      <ConnectionBanner />
      <main className="page">
        <Routes>
          <Route path="/" element={<LiveBoard />} />
          <Route path="/pivot/:id" element={<PivotDetail />} />
          <Route path="/whatif/:id" element={<WhatIfLab />} />
          <Route path="/trace" element={<AgentTraces />} />
          <Route path="/trace/:id" element={<AgentTraces />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </MatchProvider>
  );
}
