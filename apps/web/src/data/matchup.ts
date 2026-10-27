// The line-up from your team's side (Ax69, #322): which of your lines faces which of theirs, where
// your side has a spare player and where it is short, and how the two coaches' plans differ, told
// from the ♥ team. Worked out here from both team sheets and tactics; momomojun's prematch endpoint
// (#314) sends the same `matchup.lines` / `matchup.tactics_diff`, and its lines win when it has them.
import type { TeamSheet, TeamTactics } from "@pivot/contracts";
import { other } from "./persona";
import type { Side } from "./view";

type Role = TeamSheet["starters"][number]["role"];

/** A zone of the pitch, named from the viewer's team: its left flank faces the other team's right. */
export const ZONES = ["left", "middle", "right", "attack", "defence"] as const;
export type Zone = (typeof ZONES)[number];
export type Edge = "edge" | "even" | "short";
export type Line = { zone: Zone; mine: Role[]; theirs: Role[]; edge: Edge };

const LEFT: readonly Role[] = ["LB", "LWB", "LM", "LW"];
const RIGHT: readonly Role[] = ["RB", "RWB", "RM", "RW"];
const MIDDLE: readonly Role[] = ["DM", "CM", "AM"];

/** Who stands in each zone, for my team and for theirs. My left flank meets their right. */
const MEETS: Record<Zone, [readonly Role[], readonly Role[]]> = {
  left: [LEFT, RIGHT],
  right: [RIGHT, LEFT],
  middle: [MIDDLE, MIDDLE],
  attack: [["ST"], ["CB"]],
  defence: [["CB"], ["ST"]],
};

const roles = (sheet: TeamSheet, pick: readonly Role[]) =>
  sheet.starters.slice().sort((a, b) => a.slot - b.slot).map((s) => s.role).filter((r) => pick.includes(r));

const edgeOf = (mine: number, theirs: number): Edge => (mine > theirs ? "edge" : mine < theirs ? "short" : "even");

/** The #314 shape of one line: roles per side, keyed by the zone's name from the home side. */
export type ApiLine = { zone: string; home: string[]; away: string[]; note?: string };

/** #314 names its zones from the home side ("home_wide_left"); the same zone seen from `side`. */
function zoneFrom(apiZone: string, side: Side): Zone | null {
  const z = apiZone.replace(/^(home|away)_/, "");
  const flip = side === "away" !== apiZone.startsWith("away_");
  if (/left/.test(z)) return flip ? "right" : "left";
  if (/right/.test(z)) return flip ? "left" : "right";
  if (/mid/.test(z)) return "middle";
  if (/attack|forward|front/.test(z)) return flip ? "defence" : "attack";
  if (/defen|back/.test(z)) return flip ? "attack" : "defence";
  return null;
}

/** The lines from the picked team's side: from #314's lines when it sent any, else from the two sheets. */
export function lines(sheets: Record<Side, TeamSheet>, side: Side, api?: readonly ApiLine[] | null): Line[] {
  if (api?.length) {
    const out = api.flatMap((l) => {
      const zone = zoneFrom(l.zone, side);
      if (!zone) return [];
      const mine = l[side] as Role[];
      const theirs = l[other(side)] as Role[];
      return [{ zone, mine, theirs, edge: edgeOf(mine.length, theirs.length) }];
    });
    if (out.length) return ZONES.flatMap((z) => out.filter((l) => l.zone === z));
  }
  return ZONES.map((zone) => {
    const [m, th] = MEETS[zone];
    const mine = roles(sheets[side], m);
    const theirs = roles(sheets[other(side)], th);
    return { zone, mine, theirs, edge: edgeOf(mine.length, theirs.length) };
  }).filter((l) => l.mine.length + l.theirs.length > 0);
}

/** The settings with an order (low to high), as in TeamTactics' meters. */
export const SCALES = {
  press: ["low", "mid", "high"],
  line_height: ["low", "mid", "high"],
  width: ["narrow", "normal", "wide"],
  tempo: ["slow", "normal", "fast"],
  passing: ["short", "mixed", "direct"],
} as const satisfies Partial<Record<keyof TeamTactics, readonly string[]>>;
export type Scale = keyof typeof SCALES;
export type Diff =
  | { field: Scale; mine: string; theirs: string; more: boolean }
  | { field: "attack_focus"; mine: TeamTactics["attack_focus"]; theirs: TeamTactics["attack_focus"] }
  | { field: "counter_attack"; mine: boolean };

/** Where the two plans differ, from the picked team: "you press higher", "they play more direct". */
export function tacticsDiff(plans: Record<Side, TeamTactics>, side: Side): Diff[] {
  const me = plans[side];
  const them = plans[other(side)];
  const out: Diff[] = [];
  for (const field of Object.keys(SCALES) as Scale[]) {
    const steps = SCALES[field] as readonly string[];
    const a = steps.indexOf(me[field]);
    const b = steps.indexOf(them[field]);
    if (a !== b) out.push({ field, mine: me[field], theirs: them[field], more: a > b });
  }
  if (me.attack_focus !== them.attack_focus) out.push({ field: "attack_focus", mine: me.attack_focus, theirs: them.attack_focus });
  if (me.counter_attack !== them.counter_attack) out.push({ field: "counter_attack", mine: me.counter_attack });
  return out;
}

/** Pick a team or a player to follow, or let go of it when it is the one picked already (♥ and ☆). */
export const toggled = <V extends string>(current: V | null, v: V): V | null => (current === v ? null : v);
