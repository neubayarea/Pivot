// "Start demo" / "Start match". The API has no endpoint to start a match yet, so this asks for
// POST /api/dev/demo/start and, until that exists (or whenever it fails), switches the page to
// the local fixture replay from kick-off. Either way the viewer ends up watching a match.
import { api } from "./live/api";
import { fixtureMode } from "./match";

export const REPLAY_URL = "/?fixture=1&from=0";

export async function startDemo(matchId?: string, go: (url: string) => void = (u) => window.location.assign(u)) {
  if (fixtureMode()) return go(REPLAY_URL);
  try {
    const { match_id } = await api.startDemo(matchId);
    go(`/?match=${encodeURIComponent(match_id)}`);
  } catch {
    go(REPLAY_URL);
  }
}
