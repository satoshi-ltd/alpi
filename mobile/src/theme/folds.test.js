import { describe, expect, it } from "vitest";
import { ACCENTS, ACCENT_FOLDS, ACCENT_HEXES, accentName, nearestAccent, pairName, selectedAccent } from "../../../common/accents.mjs";
import { DEFAULT_FOLD, FOLD_IDS, foldPolygons, foldTones, normaliseFold, toOklab } from "../../../common/folds.mjs";
import { foldProblems } from "../../../common/folds.rules.mjs";

describe("folds", () => {
  it("keeps every object an origami model that passes the gate", () => {
    expect(foldProblems()).toEqual([]);
  });

  it("pairs every colour with one object, and every object with one colour", () => {
    expect(Object.keys(ACCENT_FOLDS).sort()).toEqual(ACCENTS.map(([name]) => name).sort());
    expect(Object.values(ACCENT_FOLDS).sort()).toEqual([...FOLD_IDS].sort());
  });

  it("reads an unknown or missing fold as the diamond", () => {
    expect(DEFAULT_FOLD).toBe("diamond");
    expect([undefined, null, "", "pencil", 3, ["heart"]].map(normaliseFold)).toEqual(Array(6).fill("diamond"));
    expect(normaliseFold(" Heart ")).toBe("heart");
  });

  it("derives three tones from one colour and keeps the colour as the base", () => {
    for (const hex of ACCENT_HEXES) {
      const [light, base, shade] = foldTones(hex);
      expect(base).toBe(hex);
      expect(new Set([light, base, shade]).size).toBe(3);
    }
    expect(foldTones("#f0b447")).toEqual(["#ffdeab", "#f0b447", "#bc860e"]);
  });

  it("draws one inset polygon per facet", () => {
    const polygons = foldPolygons("shield", "#3899e2", 64);
    expect(polygons).toHaveLength(4);
    for (const { points, fill } of polygons) {
      expect(fill).toMatch(/^#[0-9a-f]{6}$/);
      for (const [x, y] of points) expect(x >= -1 && x <= 101 && y >= -1 && y <= 101).toBe(true);
    }
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

  it("draws any input, falling back to amber for a colour it cannot read", () => {
    expect(foldTones("#fff")).toEqual(foldTones("#ffffff"));
    expect(foldTones("red")).toEqual(foldTones("#f0b447"));
    expect(foldTones(undefined)).toEqual(foldTones("#f0b447"));
  });

  it("holds twelve hues and no grey, so no profile reads as the ink alpaca", () => {
    expect(ACCENTS).toHaveLength(12);
    for (const [name, hex] of ACCENTS) {
      const [, a, b] = toOklab(hex);
      expect(Math.hypot(a, b), name).toBeGreaterThan(0.08);
    }
  });

  it("names a pair by its colour and object", () => {
    expect(pairName("shield", "#3899e2")).toBe("blue shield");
    expect(pairName(undefined, "#f0b447")).toBe("amber diamond");
    expect(accentName("#7e8792")).toBe("sky");
  });
});
