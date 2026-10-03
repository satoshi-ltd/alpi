import { describe, expect, it } from "vitest";
import { ACCENT_HEXES } from "../../../common/accents.mjs";
import { CREASE_MIN_CONTRAST, contrastRatio, creaseGradient, creaseTones } from "../../../common/crease.mjs";
import { palettes } from "../../../common/tokens.mjs";

const GROUNDS = [palettes.light.bgPane, palettes.light.bg, palettes.dark.bgPane, palettes.dark.bg];

describe("crease type", () => {
  it.each(GROUNDS)("keeps three distinct tones readable on %s for every colour", (ground) => {
    for (const accent of ACCENT_HEXES) {
      const tones = creaseTones(accent, ground);
      expect(tones, accent).toHaveLength(3);
      expect(new Set(tones).size, accent).toBe(3);
      for (const tone of tones) {
        expect(tone).toMatch(/^#[0-9a-f]{6}$/);
        expect(contrastRatio(tone, ground), `${accent} ${tone}`).toBeGreaterThanOrEqual(CREASE_MIN_CONTRAST);
      }
    }
  });

  it("starts from the profile's own colour when it already reads", () => {
    expect(creaseTones("#6572e4", palettes.dark.bgPane)[0]).toBe("#6572e4");
  });

  it("falls back to neutral inks for a colour it cannot read", () => {
    const tones = creaseTones("red", palettes.light.bgPane);
    expect(tones).toHaveLength(3);
    for (const tone of tones) expect(contrastRatio(tone, palettes.light.bgPane)).toBeGreaterThanOrEqual(CREASE_MIN_CONTRAST);
  });

  it("cuts the gradient in three bands with a slit between", () => {
    const gradient = creaseGradient(["#111111", "#222222", "#333333"]);
    expect(gradient.startsWith("linear-gradient(115deg")).toBe(true);
    expect(gradient.match(/transparent/g)).toHaveLength(2);
    for (const tone of ["#111111", "#222222", "#333333"]) expect(gradient).toContain(tone);
  });
});
