import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import App from "./App";
import { DEMO_MATCH_ID, readSavedMatch } from "./data/choice";
import ErrorBoundary from "./components/ErrorBoundary";
import { PrefsProvider } from "./i18n";
import Overlay from "./pages/Overlay";
import "./styles/tokens.css";
import "./styles/base.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PrefsProvider>
      <BrowserRouter>
        <Routes>
          {/* The broadcast overlay stands alone: no top bar, no live-board feed, transparent page. */}
          <Route path="/overlay/:matchId" element={<Overlay />} />
          {/* `/overlay` follows the match last picked on the live board. */}
          <Route path="/overlay" element={<Navigate replace to={`/overlay/${encodeURIComponent(readSavedMatch() ?? DEMO_MATCH_ID)}${window.location.search}`} />} />
          <Route
            path="*"
            element={
              <ErrorBoundary>
                <App />
              </ErrorBoundary>
            }
          />
        </Routes>
      </BrowserRouter>
    </PrefsProvider>
  </StrictMode>,
);
