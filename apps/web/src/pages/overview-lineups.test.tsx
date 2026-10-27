// Ax69 (#322): the overview changes with fan or analyst and the ♥ team; the line-ups tab has a ☆
// beside every player and the matchup from the ♥ team's side; the score header has a ♥ per team and
// a "Following" chip. Rendered to static HTML like the other page tests, so no DOM: the toggles are
// checked through what each state renders and through the pure `toggled` they call.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import type { MatchEvent, PlayerReport, TeamSheet, TeamTactics } from "@pivot/contracts";
import { PlayerDetail } from "../components/PitchBoard";
import ScoreHeader from "../components/ScoreHeader";
import { FixtureProvider } from "../data/match";
import { lineupFacts, shortName } from "../data/lineupFacts";
import { lines, tacticsDiff, toggled } from "../data/matchup";
import { DEFAULT_PREFS, PrefsProvider, usePrefs } from "../i18n";
import LiveBoard from "./LiveBoard";

const g = globalThis as { window?: { location: { search: string }; localStorage: Pick<Storage, "getItem" | "setItem" | "removeItem"> } };
const withWindow = (search: string) => {
  const m = new Map<string, string>();
  g.window = { location: { search }, localStorage: { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v), removeItem: (k) => void m.delete(k) } };
};
afterEach(() => void delete g.window);

function Header() {
  const { prefs } = usePrefs();
  return <ScoreHeader prefs={prefs} />;
}

const render = (search: string, node = <LiveBoard />) => {
  withWindow(search);
  return renderToStaticMarkup(
    <PrefsProvider>
      <MemoryRouter initialEntries={[`/${search}`]}>
        <FixtureProvider>{node}</FixtureProvider>
      </MemoryRouter>
    </PrefsProvider>,
  );
};

describe("the overview", () => {
  it("gives an analyst the momentum line and the turning points, and no story cards", () => {
    const html = render("?fixture=1&from=95&tab=overview&mode=analyst");
    expect(html).toContain('data-audience="analyst"');
    expect(html).toContain('id="post-momentum"');
    expect(html).toContain('id="post-pivots"');
    expect(html).not.toContain('id="post-story"');
  });

  it("gives a fan the story of the match first, and the momentum line only after it", () => {
    const html = render("?fixture=1&from=95&tab=overview&mode=fan");
    expect(html).toContain('data-audience="fan"');
    expect(html).toContain("How the match was decided");
    expect(html.indexOf('id="post-story"')).toBeGreaterThan(0);
    expect(html.indexOf('id="post-story"')).toBeLessThan(html.indexOf('id="post-momentum"'));
  });

  it("opens on a different first block for a fan and an analyst (ORDER.*.post)", () => {
    const first = (html: string) => html.match(/<div class="post (?:fan|analyst)"[^>]*><header class="post-lead">.*?<\/header>(<\w+[^>]*>)/)![1];
    expect(first(render("?fixture=1&from=95&tab=overview&mode=fan"))).toContain('id="post-story"');
    expect(first(render("?fixture=1&from=95&tab=overview&mode=analyst"))).toContain('id="post-momentum"');
  });

  it("shows both the key moments and the core five stats, and the AI log last", () => {
    for (const mode of ["fan", "analyst"]) {
      const html = render(`?fixture=1&from=95&tab=overview&mode=${mode}`);
      const keys = html.indexOf('id="post-keys"');
      const core = html.indexOf('id="post-core"');
      const trace = html.indexOf('id="post-trace"');
      expect(keys).toBeGreaterThan(0);
      expect(core).toBeGreaterThan(0);
      expect(trace).toBeGreaterThan(Math.max(keys, core));
    }
  });

  it("marks each turning point for or against the ♥ team, on the momentum line and in the list", () => {
    const none = render("?fixture=1&from=95&tab=overview&mode=analyst");
    expect(none).not.toContain("lean-tag");
    expect(none).not.toContain("mk-lean");
    const html = render("?fixture=1&from=95&tab=overview&mode=analyst&team=home");
    expect(html).toMatch(/class="mk-lean (for|against)"/);
    expect(html).toMatch(/class="lean-tag (for|against)" style="--tc:var\(--pv-(home|away)\)"/);
    // The fixture's red card swings it to the home side: that one is for a home fan, against an away fan.
    expect(html).toContain('class="pr to-home lean-for"');
    expect(render("?fixture=1&from=95&tab=overview&mode=analyst&team=away")).toContain('class="pr to-home lean-against"');
  });

  it("puts the ♥ team's match first once a team is picked", () => {
    const none = render("?fixture=1&from=95&tab=overview&mode=fan");
    expect(none).not.toContain('id="you-hd"');
    const html = render("?fixture=1&from=95&tab=overview&mode=fan&team=away");
    expect(html).toContain("How Northvale Rovers did");
    expect(html.indexOf('id="you-hd"')).toBeLessThan(html.indexOf('id="post-story"'));
    expect(html).toContain("Your team&#x27;s match first");
  });
});

describe("the ♥ beside each team in the score header", () => {
  it("is off for both teams with none picked", () => {
    const html = render("?fixture=1&from=95", <Header />);
    expect(html).toContain('aria-label="Follow Harbour City"');
    expect(html).toContain('aria-label="Follow Northvale Rovers"');
    expect(html).not.toContain('aria-pressed="true"');
  });

  it("is pressed for the picked team, and pressing it again lets the team go", () => {
    const html = render("?fixture=1&from=95&team=home", <Header />);
    expect(html).toMatch(/class="fav-btn home on" aria-pressed="true" aria-label="Stop following Harbour City"/);
    expect(html).toMatch(/class="fav-btn away" aria-pressed="false" aria-label="Follow Northvale Rovers"/);
    expect(toggled("home", "home")).toBeNull();
    expect(toggled("home", "away")).toBe("away");
    expect(toggled(null, "away")).toBe("away");
  });

  it("stays in the slim bar", () => {
    withWindow("?fixture=1&from=95&team=away");
    const html = renderToStaticMarkup(
      <PrefsProvider><MemoryRouter><FixtureProvider>
        <ScoreHeader prefs={{ ...DEFAULT_PREFS, focus_team: "away" }} fold={{ slim: true, toggle: () => {} }} />
      </FixtureProvider></MemoryRouter></PrefsProvider>,
    );
    expect(html).toContain('class="mh-bar"');
    expect(html).toContain('aria-label="Stop following Northvale Rovers"');
  });
});

describe("the Following chip", () => {
  it("shows the followed player under the header with a ✕ to stop", () => {
    const html = render("?fixture=1&from=95&player=hcy-9", <Header />);
    expect(html).toContain("Following: D. Okafor");
    expect(html).toContain('aria-label="Stop following D. Okafor"');
  });

  it("is not there with no player followed", () => {
    expect(render("?fixture=1&from=95", <Header />)).not.toContain("follow-chip");
  });

  it("speaks Chinese", () => {
    expect(render("?fixture=1&from=95&player=hcy-9&lang=zh", <Header />)).toContain("正在关注：D. Okafor");
  });
});

describe("the line-ups tab", () => {
  it("puts a ☆ beside every player, and a ★ on the followed one", () => {
    const html = render("?fixture=1&from=95&tab=lineups&player=hcy-9");
    expect(html).toContain('aria-label="Follow C. Nkemelu"');
    expect(html).toMatch(/class="follow on" aria-pressed="true" aria-label="Stop following D. Okafor"><span aria-hidden="true">★/);
    expect(html.match(/class="follow on"/g)).toHaveLength(1);
    expect(toggled("hcy-9", "hcy-9")).toBeNull();
    expect(toggled("hcy-9", "hcy-7")).toBe("hcy-7");
  });

  it("asks for a team before it can show the line-up from your side", () => {
    const html = render("?fixture=1&from=95&tab=lineups");
    expect(html).toContain("Pick your team");
    expect(html).toContain('class="fav-btn home named"');
    expect(render("?fixture=1&from=95&tab=lineups&team=home")).not.toContain("Pick your team");
  });
});

const sheet = (formation: string, roles: TeamSheet["starters"][number]["role"][]): TeamSheet =>
  ({ formation, starters: roles.map((role, slot) => ({ player_id: `p${slot}`, slot, role, anchor: [0, 0] })), bench: [] }) as unknown as TeamSheet;

describe("the player clicked on the pitch", () => {
  it("has the shared Follow button", () => {
    const player = { player_id: "hcy-9", name: "D. Okafor", shirt: 9 };
    const off = render("?fixture=1&from=95", <PlayerDetail player={player} role={undefined} onBack={() => {}} />);
    expect(off).toContain('class="follow" aria-pressed="false" aria-label="Follow D. Okafor"');
    const on = render("?fixture=1&from=95&player=hcy-9", <PlayerDetail player={player} role={undefined} onBack={() => {}} />);
    expect(on).toContain('class="follow on" aria-pressed="true"');
  });
});

describe("the matchup from your side", () => {
  const home = sheet("4-3-3", ["GK", "LB", "CB", "CB", "RB", "CM", "DM", "CM", "LW", "ST", "RW"]);
  const away = sheet("3-5-2", ["GK", "CB", "CB", "CB", "LWB", "CM", "DM", "CM", "RWB", "ST", "ST"]);

  it("counts each of your lines against theirs, your left flank against their right", () => {
    const mine = lines({ home, away }, "home");
    const by = Object.fromEntries(mine.map((l) => [l.zone, l]));
    expect(by.left).toMatchObject({ mine: ["LB", "LW"], theirs: ["RWB"], edge: "edge" });
    expect(by.middle).toMatchObject({ edge: "even" });
    expect(by.attack).toMatchObject({ mine: ["ST"], theirs: ["CB", "CB", "CB"], edge: "short" });
    expect(by.defence).toMatchObject({ mine: ["CB", "CB"], theirs: ["ST", "ST"], edge: "even" });
  });

  it("turns round for the other team", () => {
    const by = Object.fromEntries(lines({ home, away }, "away").map((l) => [l.zone, l]));
    expect(by.left).toMatchObject({ mine: ["LWB"], theirs: ["RB", "RW"], edge: "short" });
    expect(by.attack).toMatchObject({ mine: ["ST", "ST"], theirs: ["CB", "CB"], edge: "even" });
  });

  it("uses the prematch endpoint's lines when it sends them, named from the home side", () => {
    const api = [{ zone: "home_wide_left", home: ["LW"], away: ["RB", "RM"] }, { zone: "midfield", home: ["CM", "DM", "CM"], away: ["DM", "AM"] }];
    expect(lines({ home, away }, "home", api)).toEqual([
      { zone: "left", mine: ["LW"], theirs: ["RB", "RM"], edge: "short" },
      { zone: "middle", mine: ["CM", "DM", "CM"], theirs: ["DM", "AM"], edge: "edge" },
    ]);
    // The away team's right flank is where the home team's left winger plays.
    expect(lines({ home, away }, "away", api)[1]).toEqual({ zone: "right", mine: ["RB", "RM"], theirs: ["LW"], edge: "edge" });
  });

  it("lists where the plans differ, from the picked team", () => {
    const base = { press: "high", line_height: "mid", width: "wide", tempo: "normal", passing: "short", attack_focus: "left", counter_attack: false } as TeamTactics;
    const them = { ...base, press: "low", passing: "direct", counter_attack: true } as TeamTactics;
    expect(tacticsDiff({ home: base, away: them }, "home")).toEqual([
      { field: "press", mine: "high", theirs: "low", more: true },
      { field: "passing", mine: "short", theirs: "direct", more: false },
      { field: "counter_attack", mine: false },
    ]);
    expect(tacticsDiff({ home: base, away: them }, "away")[0]).toEqual({ field: "press", mine: "low", theirs: "high", more: false });
  });
});

describe("what each player did, in the line-ups", () => {
  const ev = (e: Partial<MatchEvent>) => ({ team: "home", period: 1, meta: {}, ...e }) as MatchEvent;
  it("counts goals (not own goals), cards with a second yellow as red, changes and ratings", () => {
    const facts = lineupFacts([
      ev({ t: 600, type: "shot", shot_outcome: "goal", player_id: "a" }),
      ev({ t: 1200, type: "shot", shot_outcome: "goal", player_id: "a" }),
      ev({ t: 1500, type: "clearance", player_id: "b", meta: { own_goal: "true" } }),
      ev({ t: 1800, type: "card", player_id: "c", foul: { card: "yellow" } as MatchEvent["foul"] }),
      ev({ t: 2400, type: "card", player_id: "c", foul: { card: "second_yellow" } as MatchEvent["foul"] }),
      ev({ t: 3600, type: "substitution", player_id: "d", substitution: { player_off_id: "d", player_on_id: "e", reason: "tactical", slot: 9 } }),
    ], [{ player_id: "a", stats: { rating: 8.4, minutes_played: 90 } } as PlayerReport, { player_id: "x", stats: { rating: 6, minutes_played: 0 } } as PlayerReport]);
    expect(facts.get("a")).toMatchObject({ goals: 2, rating: 8.4 });
    expect(facts.get("b")?.goals ?? 0).toBe(0);
    expect(facts.get("c")).toMatchObject({ red: true });
    expect(facts.get("d")).toMatchObject({ off: 3600 });
    expect(facts.get("e")).toMatchObject({ on: 3600 });
    expect(facts.has("x")).toBe(false);
  });

  it("shows them in the list rows once the match is under way", () => {
    const html = render("?fixture=1&from=95&tab=lineups");
    expect(html).toContain('aria-label="1 goal"');
    expect(html).toContain('aria-label="Red card"');
    expect(html).toMatch(/aria-label="Came on at \d+′"/);
    expect(html).toMatch(/aria-label="Went off at \d+′"/);
  });

  it("cuts long surnames on the pitch", () => {
    expect(shortName("Rasfelrassen")).toBe("Rasfelr.");
    expect(shortName("Okafor")).toBe("Okafor");
  });
});
