import { Route, Routes } from "react-router-dom";
import ConnectionBanner from "./components/ConnectionBanner";
import StartupScreen from "./components/StartupScreen";
import TopBar from "./components/TopBar";
import { MatchProvider } from "./data/match";
import { usePrefs } from "./i18n";
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

  return (
    <MatchProvider fallback={WAITING}>
      <TopBar prefs={prefs} onPrefsChange={setPrefs} />
      <ConnectionBanner />
      {/* The viewer's team tints the cards (base.css, `--pv-fav`). */}
      <main className="page" data-fav={prefs.focus_team ?? undefined}>
        <Routes>
          <Route path="/" element={<LiveBoard />} />
          <Route path="/pivot/:id" element={<PivotDetail />} />
          <Route path="/whatif/:id" element={<WhatIfLab />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </MatchProvider>
  );
}
