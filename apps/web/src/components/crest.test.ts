import { describe, expect, it } from "vitest";
import { CRESTS, crestSrc } from "./Crest";

describe("club crests (Dx12)", () => {
  it("maps a club's short name to its PNG, any case", () => {
    expect(crestSrc("TES")).toBe("/crests/tes.png");
    expect(crestSrc(" van ")).toBe("/crests/van.png");
  });
  it("has no crest for an unknown club, so the kit dot shows", () => {
    expect(crestSrc("XYZ")).toBeNull();
    expect(crestSrc(undefined)).toBeNull();
  });
  it("knows all 20 clubs", () => {
    expect(CRESTS.size).toBe(20);
  });
});
