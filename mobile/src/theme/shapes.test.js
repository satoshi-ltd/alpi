import { describe, expect, it } from "vitest";
import { ACCENTS, ACCENT_SHAPES, ACCENT_HEXES, accentName, nearestAccent, pairName, selectedAccent } from "../../../common/accents.mjs";
import * as agentMarks from "../../../common/agentMarks.mjs";
import { DEFAULT_SHAPE, SHAPE_IDS, defaultAsTwin, isHexColour, profileShape, shapeOf, shiftLightness, toOklab } from "../../../common/shapes.mjs";

describe("shapes", () => {
  it("keeps the twelve shape names in the order the daemon validates", () => {
    expect(SHAPE_IDS).toEqual(["round", "squircle", "drop", "dome", "pill", "clover", "cloud", "bean", "pebble", "arch", "heart", "bell"]);
  });

  it("pairs every colour with one shape, and every shape with one colour", () => {
    expect(Object.keys(ACCENT_SHAPES).sort()).toEqual(ACCENTS.map(([name]) => name).sort());
    expect(Object.values(ACCENT_SHAPES).sort()).toEqual([...SHAPE_IDS].sort());
  });

  it("reads an unknown or missing shape as the round", () => {
    expect(DEFAULT_SHAPE).toBe("round");
    expect([undefined, null, "", "pencil", 3, ["heart"]].map(shapeOf)).toEqual(Array(6).fill("round"));
    expect(shapeOf(" Heart ")).toBe("heart");
  });

  it("passes shape names through, knows no legacy id and reads only the shape field", () => {
    expect("LEGACY_SHAPE" in agentMarks).toBe(false);
    for (const shape of [...SHAPE_IDS, "twin", "honeycomb"]) expect(shapeOf(shape)).toBe(shape);
    for (const legacy of ["shield", "rocket", "crown", "alpaca"]) expect(shapeOf(legacy)).toBe("round");
    expect(profileShape({ shape: "bell" })).toBe("bell");
    expect(profileShape({ fold: "shield" })).toBe("round");
    expect(profileShape({ shape: "pill", fold: "shield" })).toBe("pill");
    expect(profileShape(null)).toBe("round");
  });

  it("gives the default profile Twin and leaves a fold untranslated", () => {
    const twin = defaultAsTwin("#14110c");
    expect(twin({ name: "default", shape: "round", accent: null })).toMatchObject({ shape: "twin", accent: "#14110c" });
    expect(twin({ name: "doc", fold: "shield" })).toEqual({ name: "doc", fold: "shield" });
    expect(twin({ name: "doc", shape: "pill" })).toEqual({ name: "doc", shape: "pill" });
  });

  it("shifts a colour's lightness in either direction and keeps it a six-digit hex", () => {
    for (const hex of ACCENT_HEXES) {
      const [L] = toOklab(hex);
      const lighter = shiftLightness(hex, 0.1);
      const darker = shiftLightness(hex, -0.1);
      expect(isHexColour(lighter) && isHexColour(darker)).toBe(true);
      expect(toOklab(lighter)[0]).toBeGreaterThan(L);
      expect(toOklab(darker)[0]).toBeLessThan(L);
    }
    expect(shiftLightness("#ffffff", 0.5)).toMatch(/^#f[0-9a-f]f[0-9a-f]f[0-9a-f]$/);
    expect(shiftLightness("#000000", -0.5)).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("tells a six-digit hex colour from anything else", () => {
    expect(["#3899e2", "#ABCDEF"].map(isHexColour)).toEqual([true, true]);
    expect(["#fff", "red", "", null, undefined, "#3899e2 "].map(isHexColour)).toEqual(Array(6).fill(false));
  });

  it("maps a stored colour to the nearest of the twelve", () => {
    for (const [name, hex] of ACCENTS) expect(nearestAccent(hex)).toEqual([name, hex]);
    const previous = {
      "#f0b447": "amber", "#d97757": "vermilion", "#c14545": "vermilion", "#c14580": "magenta", "#9d4dc6": "violet",
      "#6a6dd6": "indigo", "#3d7ea6": "blue", "#2f8e9e": "sky", "#2f7d6e": "teal", "#3fb37a": "green", "#8a7a4a": "amber",
    };
    for (const [old, name] of Object.entries(previous)) expect(nearestAccent(old)[0], old).toBe(name);
    expect(nearestAccent("not a colour")).toBeNull();
    expect(nearestAccent("#6c7480")).toBeNull();
    expect(nearestAccent("#7e8792")).toEqual(["sky", "#3ac9f3"]);
  });

  it("selects the exact swatch, else the nearest, else none", () => {
    expect(selectedAccent("#F0B447")).toBe("#f0b447");
    expect(selectedAccent("#3d7ea6")).toBe("#3899e2");
    expect(selectedAccent("red")).toBeNull();
  });

  it("shifts any input, reading three-digit hex and falling back to amber for a colour it cannot read", () => {
    expect(shiftLightness("#fff", -0.2)).toBe(shiftLightness("#ffffff", -0.2));
    expect(shiftLightness("red", 0.1)).toBe(shiftLightness("#f0b447", 0.1));
    expect(shiftLightness(undefined, 0.1)).toBe(shiftLightness("#f0b447", 0.1));
  });

  it("holds twelve hues and no grey, so no profile reads as the ink brand mark", () => {
    expect(ACCENTS).toHaveLength(12);
    for (const [name, hex] of ACCENTS) {
      const [, a, b] = toOklab(hex);
      expect(Math.hypot(a, b), name).toBeGreaterThan(0.08);
    }
  });

  it("names a pair by its colour and its shape", () => {
    expect(pairName("bell", "#3899e2")).toBe("blue bell");
    expect(pairName("shield", "#3899e2")).toBe("blue round");
    expect(pairName("pencil", "#3899e2")).toBe("blue round");
    expect(pairName(undefined, "#f0b447")).toBe("amber round");
    expect(accentName("#7e8792")).toBe("sky");
  });
});
