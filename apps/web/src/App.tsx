import { useState } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import ConnectionBanner, { MissingMatchBanner } from "./components/ConnectionBanner";
import KitColours from "./components/KitColours";
import Playback from "./components/Playback";
import ScoreHeader from "./components/ScoreHeader";
import StartupScreen from "./components/StartupScreen";
import TopBar from "./components/TopBar";
import WatchPrompt from "./components/WatchPrompt";
import { useHeaderFold } from "./data/headerFold";
import { MatchProvider, fixtureMode } from "./data/match";
import { usePrefs } from "./i18n";
import AgentTraces from "./pages/AgentTraces";
import Hub, { isHubPage } from "./pages/Hub";
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

export default function App() {
  const { prefs, setPrefs } = usePrefs();
  const fold = useHeaderFold();
  const { pathname, search } = useLocation();
  // Decided once, as in MatchProvider: in-app links drop `?fixture=1`.
  const [fixture] = useState(() => fixtureMode());

  // C14: `/` with no match in the link is the match centre; a match opens under it as before.
  if (!fixture && isHubPage(pathname, search)) return <Hub />;

  return (
    <MatchProvider fallback={WAITING}>
      <KitColours />
      <TopBar prefs={prefs} onPrefsChange={setPrefs} />
      {/* C13: asked once, on a first visit: fan or analyst. */}
      <WatchPrompt />
      <ConnectionBanner />
      <MissingMatchBanner />
      {/* Ax59: the score and the replay bar stay at the top of the window while the page scrolls;
          Ax66: the score folds to a slim bar once scrolled past (data/headerFold.ts). */}
      <div ref={fold.anchor} className="match-head-anchor" aria-hidden="true" />
      <div ref={fold.head} className="match-head">
        <ScoreHeader prefs={prefs} fold={fold} />
        <Playback />
      </div>
      {/* The viewer's team tints the cards (base.css, `--pv-fav`). */}
      <main className="page" data-fav={prefs.focus_team ?? undefined}>
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
