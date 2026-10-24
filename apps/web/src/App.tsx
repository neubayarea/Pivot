import { useState } from "react";
import { Route, Routes } from "react-router-dom";
import type { ViewerPrefs } from "@pivot/contracts";
import TopBar from "./components/TopBar";
import { MatchProvider } from "./data/match";
import AgentTraces from "./pages/AgentTraces";
import LiveBoard from "./pages/LiveBoard";
import NotFound from "./pages/NotFound";
import PivotDetail from "./pages/PivotDetail";
import WhatIfLab from "./pages/WhatIfLab";

const DEFAULT_PREFS: ViewerPrefs = {
  audience: "analyst",
  language: "en",
  focus_team: null,
  focus_player_id: null,
};

export default function App() {
  const [prefs, setPrefs] = useState<ViewerPrefs>(DEFAULT_PREFS);

  return (
    <MatchProvider>
      <TopBar prefs={prefs} onPrefsChange={setPrefs} />
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
