// QA round 4 (#354, #355): the ♥ follows the club, a replay never says Live, the picker names a
// fixture, the Chinese names have room, and one moment is not "1 moments".
import { describe, expect, it } from "vitest";
import type { Match } from "@pivot/contracts";
import { translator } from "../i18n";
import { en } from "../i18n/messages/en";
import { es } from "../i18n/messages/es";
import { zh } from "../i18n/messages/zh";
import { matchLabel, matchdayOf } from "./choice";
import { savedClub, sideOfClub } from "./followClub";
import { onAir, type MatchView } from "./view";

const HBC_ROV = { home: { short_name: "HBC" }, away: { short_name: "ROV" } };
const LUN_HBC = { home: { short_name: "LUN" }, away: { short_name: "HBC" } };

describe("the ♥ team is a club (#354)", () => {
  it("is on whichever side the club plays", () => {
    expect(sideOfClub(HBC_ROV, "HBC")).toBe("home");
    expect(sideOfClub(LUN_HBC, "HBC")).toBe("away");
    expect(sideOfClub(LUN_HBC, "ROV")).toBeNull();
  });
  it("reads a choice saved before clubs were as that side of Harbour City v Northgate Rovers", () => {
    expect(savedClub(null, "home")).toBe("HBC");
    expect(sideOfClub(LUN_HBC, savedClub(null, "home"))).toBe("away");
    expect(savedClub("LUN", "away")).toBe("LUN");
    expect(savedClub(null, null)).toBeNull();
  });
});

describe("only a match being played says Live (#354)", () => {
  const at = (status: string, playback: MatchView["playback"]) =>
    ({ match: { status }, playback } as unknown as Pick<MatchView, "match" | "playback">);
  const controls = { playing: true, setPlaying: () => {}, setSpeed: () => {}, restart: () => {}, seek: () => {}, end: 5400 };
  it("is live on the live feed and on the hub's wall-clock match", () => {
    expect(onAir(at("live", null))).toBe(true);
    expect(onAir(at("live", { ...controls, goLive: () => {} }))).toBe(true);
  });
  it("is a replay when a finished match is played again", () => {
    expect(onAir(at("live", controls))).toBe(false);
    expect(onAir(at("paused", controls))).toBe(false);
    expect(onAir(at("finished", null))).toBe(false);
  });
});

describe("the picker names a next-round fixture (#354)", () => {
  const fixture = {
    match_id: "S2026-31-LUN-HBC", status: "scheduled",
    home: { name: "Lunsford Sporting", short_name: "LUN" }, away: { name: "Harbour City", short_name: "HBC" },
  } as unknown as Match;
  it("by its clubs and matchday, never its id", () => {
    expect(matchLabel(fixture, translator("en"))).toBe("Lunsford Sporting v Harbour City · MD31");
    expect(matchLabel(fixture, translator("zh"))).toBe("Lunsford Sporting v Harbour City · 第 31 轮");
    expect(matchdayOf("M-seed-101")).toBeNull();
  });
});

describe("Chinese has a space around a club or venue name (#355)", () => {
  it("in every pre-match and matchup sentence", () => {
    const tight = Object.entries(zh).filter(([k, v]) => /^(pre|prematch\.rotation|mu)\./.test(k) &&
      /[一-鿿]\{(team|opp|opponent|venue|competition)\}|\{(team|opp|opponent|venue|competition)\}[一-鿿]/.test(v ?? ""));
    expect(tight).toEqual([]);
    expect(translator("zh")("pre.vsAway", { team: "Elmshaw Athletic" })).toBe("客场对 Elmshaw Athletic");
    // {rested} is Chinese and brings its own space: " 3 名主力".
    expect(translator("zh")("prematch.rotation.cup_benched", { days: 3, to: "客场对", opponent: "Eastmoor", competition: "Freeland Cup",
      stage: "半决赛", rested: translator("zh")("pre.restedMany", { n: 3 }) })).toBe("3 天后客场对 Eastmoor 打 Freeland Cup 半决赛（虚构赛程），主教练让 3 名主力休息。");
  });
});

describe("one moment so far is not \"1 moments\" (#354)", () => {
  it("in English and Spanish", () => {
    expect(translator("en")("moments.titleLive", { n: 1 })).not.toMatch(/\b1 moments\b/);
    expect(translator("es")("moments.titleLive", { n: 1 })).not.toMatch(/\b1 momentos\b/);
    expect(en["moments.titleLive"]).toContain("{n}");
    expect(es["moments.titleLive"]).toContain("{n}");
  });
});
