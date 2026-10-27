// Ax42: what each key moment's clip covers, clip time across cut parts, and the speeds. The ranges
// run on hand-made events and on the M-seed-29 demo match (38′ red, 40′ goal, 46′ penalty VAR took
// back, 60′ penalty saved). Then the board: a picked key moment opens its clip, the others do not.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { Match, MatchEvent } from "@pivot/contracts";
import KeyMoments from "../components/KeyMoments";
// a recorded match that never changes (eval/frozen/README.md: M-seed-29 before Ax44)
import demo from "../../../../eval/frozen/m-seed-29-before-ax44.json";
import { advance, clipLength, fromShot, keyClip, MAX_STEP_MS, nextRate, partAt, penaltyKick, RATES, toClip, toMatch } from "./clips";
import { keyMoments } from "./keyMoments";
import { toView } from "./live/provider";
import { MatchContext } from "./match";
import { shotClips } from "./setpieces";

let seq = 0;
const ev = (o: Partial<MatchEvent>) =>
  ({ event_id: `e${++seq}`, seq, t: 0, period: 1, period_t: 0, team: "home", type: "pass", meta: {}, pass_type: null, play_pattern: "open_play",
    possession_id: 1, player_id: "h9", receiver_id: null, location: [50, 34], end_location: null, shot_outcome: null, foul: null, var: null,
    keeper_action: null, xg: null, clock_label: "1'", substitution: null, team_sheet: null, ...o }) as MatchEvent;

describe("clip time", () => {
  const parts = [[100, 111], [180, 186]] as const;

  it("adds the parts up and skips the cut between them", () => {
    expect(clipLength(parts)).toBe(17);
    expect(toMatch(parts, 0)).toBe(100);
    expect(toMatch(parts, 11)).toBe(111);
    expect(toMatch(parts, 12.5)).toBe(181.5);
    expect(toMatch(parts, 99)).toBe(186);
    expect(toClip(parts, 105)).toBe(5);
    expect(toClip(parts, 150)).toBe(11);       // in the cut: the start of the next part
    expect(toClip(parts, 183)).toBe(14);
    expect(partAt(parts, 10.9)).toBe(0);
    expect(partAt(parts, 11.1)).toBe(1);
    expect(partAt(parts, 17)).toBe(1);
  });

  it("moves by real time times the speed, smoothly at any of the five speeds", () => {
    expect(RATES).toEqual([0.25, 0.5, 1, 2, 5]);
    // One 60 Hz screen frame: a quarter speed moves 4 ms of match time, five times speed 83 ms.
    expect(advance(0, 1000 / 60, 0.25, 10)).toBeCloseTo(0.25 / 60);
    expect(advance(0, 1000 / 60, 5, 10)).toBeCloseTo(5 / 60);
    // A second of screen frames at each speed covers that many seconds of match.
    for (const r of RATES) {
      let c = 0;
      for (let i = 0; i < 60; i++) c = advance(c, 1000 / 60, r, 100);
      expect(c).toBeCloseTo(r);
    }
    // A long stall (a hidden tab) moves no more than one step; the end is the end.
    expect(advance(0, 5000, 1, 10)).toBe(MAX_STEP_MS / 1000);
    expect(advance(9.99, 100, 5, 10)).toBe(10);
  });

  it("steps through the speeds and stops at the ends", () => {
    expect(nextRate(1, 1)).toBe(2);
    expect(nextRate(5, 1)).toBe(5);
    expect(nextRate(0.5, -1)).toBe(0.25);
    expect(nextRate(0.25, -1)).toBe(0.25);
  });
});

describe("key moment clips", () => {
  it("a goal: the start of the attack (at most 15 s) to 3 s after", () => {
    const long = [ev({ t: 50, possession_id: 4 }), ev({ t: 70, possession_id: 4, type: "carry" }),
      ev({ t: 78, possession_id: 4, type: "shot", shot_outcome: "goal", location: [95, 34], end_location: [105, 33] })];
    const k = keyMoments(long, true)[0];
    const c = keyClip(k, long);
    expect(c.parts).toEqual([[63, 81]]);
    expect(c.shot).toBe(long[2]);
    expect(c.marks).toEqual([{ t: 78, kind: "goal", side: "home", at: [95, 34] }]);
    const quick = [ev({ t: 200, possession_id: 9 }), ev({ t: 202, possession_id: 9, type: "shot", shot_outcome: "goal" })];
    expect(keyClip(keyMoments(quick, true)[0], quick).parts).toEqual([[197, 205]]);   // at least 5 s before
  });

  it("an own goal counts the attack of the side it counts for", () => {
    const evs = [ev({ t: 300, team: "away", possession_id: 3 }), ev({ t: 306, team: "home", type: "clearance", possession_id: 3, meta: { own_goal: "true" } })];
    const k = keyMoments(evs, true)[0];
    expect(k.side).toBe("away");
    expect(keyClip(k, evs).parts).toEqual([[300, 309]]);
  });

  it("a penalty that goes in runs on to the goal; a long wait for the kick is cut", () => {
    const foul = ev({ t: 1000, team: "away", type: "foul", player_id: "a4", location: [99, 30], foul: { penalty_awarded: true, card: null } as unknown as MatchEvent["foul"] });
    const kickLate = ev({ t: 1090, type: "shot", shot_outcome: "goal", location: [94, 34], end_location: [105, 36] });
    const late = [foul, kickLate];
    const k = keyMoments(late, true).find((x) => x.kind === "penalty")!;
    expect(penaltyKick(late, foul)).toBe(kickLate);
    const c = keyClip(k, late);
    expect(c.parts).toEqual([[992, 1003], [1087, 1093]]);
    expect(c.named).toBe("a4");
    expect(c.marks.map((m) => m.kind)).toEqual(["penalty", "goal"]);

    const soon = [foul, ev({ t: 1008, type: "shot", shot_outcome: "goal", play_pattern: "penalty", location: [94, 34] })];
    expect(keyClip(k, soon).parts).toEqual([[992, 1011]]);
    // Saved, or a shot that is not from the spot: only the foul.
    const saved = [foul, ev({ t: 1090, type: "shot", shot_outcome: "saved", location: [94, 34] })];
    expect(keyClip(k, saved).parts).toEqual([[992, 1003]]);
    expect(penaltyKick([foul, ev({ t: 1010, type: "shot", location: [88, 20] })], foul)).toBeNull();
  });

  // The demo match, as the board loads it.
  const fx = demo as unknown as { match: Match; events: MatchEvent[] };
  const keys = keyMoments(fx.events, true);
  const clipOf = (kind: string, t: number) => keyClip(keys.find((k) => k.kind === kind && k.event.t === t)!, fx.events);

  it("M-seed-29: the 38′ red from 8 s before the foul, the 40′ goal from its corner", () => {
    const red = clipOf("red", 2220);
    expect(red.parts).toEqual([[2212, 2223]]);
    expect(red.named).toBe("a04");
    expect(red.marks).toEqual([{ t: 2220, kind: "red", side: "away", at: [78.4, 51.2] }]);
    const goal = clipOf("goal", 2391);
    const [[from, to]] = goal.parts;
    expect(to).toBe(2394);
    expect(2391 - from).toBeGreaterThanOrEqual(5);
    expect(2391 - from).toBeLessThanOrEqual(15);
    // Same start as the shot's own clip, which stops 2 s after the shot instead.
    const shot = shotClips(fx.events).find((c) => c.shot.t === 2391)!;
    expect(shot.from).toBe(from);
    expect(fromShot(shot).parts).toEqual([[from, 2393]]);
  });

  it("M-seed-29: the penalty VAR took back, and the 60′ penalty that was saved", () => {
    expect(clipOf("penalty", 2972).parts).toEqual([[2964, 2975]]);
    const v = clipOf("var", 2972);
    expect(v.parts).toEqual([[2964, 2975]]);
    expect(v.marks.map((m) => m.kind)).toEqual(["penalty", "var"]);
    // Kicked 87 s later and saved: the clip stays with the foul.
    expect(penaltyKick([...fx.events].sort((a, b) => a.t - b.t || a.seq - b.seq), keys.find((k) => k.event.t === 3605)!.event)?.t).toBe(3692);
    expect(clipOf("penalty", 3605).parts).toEqual([[3597, 3608]]);
  });
});

describe("the key moments list", () => {
  const fx = demo as unknown as { match: Match; events: MatchEvent[] };
  // The fixture file has no clock labels; the API adds them.
  const events = fx.events.map((e) => ({ ...e, clock_label: `${Math.floor(e.t / 60) + 1}'` }));
  const view = toView({ match: fx.match, events: [...events].reverse(), metrics: [], pivots: [] });
  const keys = keyMoments(view.events, true);
  const render = (selected: string | null, playback: boolean) =>
    renderToStaticMarkup(
      <MemoryRouter>
        <MatchContext.Provider value={{ ...view, playback: playback ? ({ seek: () => {}, setPlaying: () => {} } as unknown as typeof view.playback) : null }}>
          <KeyMoments moments={keys} pivots={[]} windows={() => undefined} selected={selected} onPick={() => {}} />
        </MatchContext.Provider>
      </MemoryRouter>,
    );

  it("opens the picked moment's clip under it, with all five speeds, and moves the main replay only when asked", () => {
    const red = keys.find((k) => k.kind === "red")!;
    expect(render(null, true)).not.toContain("km-clip");
    const html = render(red.event.event_id, true);
    expect(html.match(/class="km-clip"/g)).toHaveLength(1);
    expect(html).toContain('aria-expanded="true"');
    for (const r of RATES) expect(html).toContain(`>${r}×</button>`);
    expect(html).toContain("8 s before the foul to 3 s after the card");
    expect(html).toContain("In the main replay");
    expect(html).toContain("Play again");
    // A match not being replayed offers the replay from there instead.
    expect(render(red.event.event_id, false)).toContain("Replay from here");
  });
});
