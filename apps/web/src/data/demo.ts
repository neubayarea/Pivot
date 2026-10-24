// "Start demo" / "Start match": replays the chosen stored match from kick-off in the browser
// (`?match=…&from=0`, data/live/replay). With no match to name, or on the fixture, it plays the
// local demo-1021 fixture instead. Either way the viewer ends up watching a match.
import { fixtureMode } from "./match";

export const REPLAY_URL = "/?fixture=1&from=0";

export const replayUrl = (matchId: string) => `/?match=${encodeURIComponent(matchId)}&from=0`;

export function startDemo(matchId?: string, go: (url: string) => void = (u) => window.location.assign(u)) {
  go(fixtureMode() || !matchId ? REPLAY_URL : replayUrl(matchId));
}
