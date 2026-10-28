import { useState } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import Wordmark from "./components/Wordmark";
import ConnectionBanner, { MissingMatchBanner } from "./components/ConnectionBanner";
import KitColours from "./components/KitColours";
import Playback from "./components/Playback";
import { MatchHead } from "./components/ScoreHeader";
import StartupScreen from "./components/StartupScreen";
import TopBar from "./components/TopBar";
import WatchPrompt from "./components/WatchPrompt";
import { FollowClub, FollowClubOnHub } from "./data/followClub";
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
      <Wordmark />
    </header>
    <ConnectionBanner />
    <main className="page">
      <StartupScreen />
    </main>
  </>
);

export default function App() {
  const { prefs, setPrefs } = usePrefs();
  const { pathname, search } = useLocation();
  // Decided once, as in MatchProvider: in-app links drop `?fixture=1`.
  const [fixture] = useState(() => fixtureMode());

  // C14: `/` with no match in the link is the match centre; a match opens under it as before.
  if (!fixture && isHubPage(pathname, search)) return <><FollowClubOnHub /><Hub /></>;

  return (
    <MatchProvider fallback={WAITING}>
      <KitColours />
      {/* #354: the ♥ team is the club, whichever side it plays on. */}
      <FollowClub />
      <TopBar prefs={prefs} onPrefsChange={setPrefs} />
      {/* C13: asked once, on a first visit: fan or analyst. */}
      <WatchPrompt />
      <ConnectionBanner />
      <MissingMatchBanner />
      {/* Ax59, Ax66, Ax77: the score scrolls away with the page and a slim bar with the replay bar
          under it sticks in its place (data/headerFold.ts); the match tabs stick under those. */}
      <MatchHead prefs={prefs}>
        <Playback />
      </MatchHead>
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
