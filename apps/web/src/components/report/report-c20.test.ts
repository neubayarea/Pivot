// C20 (#391): a draw that the chances made likeliest is said as a draw, never "wins 67%"; the fan's
// band colours a block only for a clear lead and names the longest spell; blocks not reached are "todo".
import { describe, expect, it } from "vitest";
import type { Phase } from "../../data/analysis";
import { deservedVerdict } from "./Deserved";
import { longestSpell, onTop } from "./FanPhases";

describe("deserved result with a draw likeliest", () => {
  const d = { n_sims: 10000, home_win: 0.11, draw: 0.67, away_win: 0.22, xpts: { home: 0.9, away: 1.3 } };
  it("agrees with a draw as a draw", () => {
    expect(deservedVerdict(d, { home: 0, away: 0 })).toEqual({ key: "rp.dsv.drawMatch", side: null, p: 0.67 });
  });
  it("disagrees with a win as a draw", () => {
    expect(deservedVerdict(d, { home: 1, away: 0 })).toMatchObject({ key: "rp.dsv.draw", side: null });
  });
});

const block = (from: number, tilt: number | null): Phase => ({
  from, to: from + 15,
  home: { xg: tilt === null ? null : 0.1, field_tilt_pct: tilt, possession_pct: tilt === null ? null : 50, ppda: null, shots: tilt === null ? null : 1 },
  away: { xg: tilt === null ? null : 0.1, field_tilt_pct: tilt === null ? null : 100 - tilt, possession_pct: tilt === null ? null : 50, ppda: null, shots: tilt === null ? null : 1 },
});

describe("who was on top when", () => {
  it("colours a clear lead only, and marks blocks not reached", () => {
    expect([block(0, 70), block(15, 52), block(30, 30), block(45, null)].map(onTop)).toEqual(["home", "even", "away", "todo"]);
  });
  it("names the longest spell", () => {
    expect(longestSpell([block(0, 70), block(15, 30), block(30, 35), block(45, 60)])).toEqual({ side: "away", from: 15, to: 45 });
    expect(longestSpell([block(0, 50), block(15, null)])).toBeNull();
  });
});
