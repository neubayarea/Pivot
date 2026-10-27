// The clubs' own kit colours drive the page (C11): tokens.css reads --pv-home-kit / --pv-away-kit
// for the score band, the momentum chart and every dot on the pitch, and lightens them at night.
import { useEffect } from "react";
import { useMatch } from "../data/match";

export default function KitColours() {
  const { teams } = useMatch();
  const home = teams.home.color;
  const away = teams.away.color;
  useEffect(() => {
    const root = document.documentElement.style;
    if (home) root.setProperty("--pv-home-kit", home);
    if (away) root.setProperty("--pv-away-kit", away);
    return () => {
      root.removeProperty("--pv-home-kit");
      root.removeProperty("--pv-away-kit");
    };
  }, [home, away]);
  return null;
}
