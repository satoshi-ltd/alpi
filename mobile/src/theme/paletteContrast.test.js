import { describe, expect, it } from "vitest";
import { palettes } from "./tokens.js";
import { ACCENT_HEXES } from "../../../common/accents.mjs";
import { mixHex, contrastText } from "../../../common/color.mjs";
import { contrastRatio } from "../../../common/palette.fixtures.mjs";

describe("palette readability", () => {
  it("checks the contrast calculation against black and white", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBe(21);
    expect(contrastRatio("#ffffff", "#ffffff")).toBe(1);
  });
  it.each(["light", "dark"])("keeps enabled text readable on %s surfaces", (mode) => {
    const colors = palettes[mode];
    for (const background of ["bg", "bgPane", "bgElev", "bgSide", "bgInput"]) {
      for (const foreground of ["ink", "ink2", "ink3", "successText", "warningText", "dangerText"]) {
        expect(contrastRatio(colors[foreground], colors[background]), `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5);
      }
    }
    expect(contrastRatio(colors.onDanger, colors.danger)).toBeGreaterThanOrEqual(4.5);
    for (const tone of ["success", "warning", "danger"]) {
      expect(contrastRatio(colors[`${tone}Text`], mixHex(colors[tone], 0.16, colors.bgPane))).toBeGreaterThanOrEqual(4.5);
    }
    for (const accent of ACCENT_HEXES) {
      expect(contrastRatio(colors.ink, mixHex(accent, 0.12, colors.bgPane))).toBeGreaterThanOrEqual(4.5);
      expect(contrastRatio(contrastText(accent), accent)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("mixes shorthand and full hexes consistently and bounds the tint", () => {
    expect(mixHex("#000", 0.5, "#fff")).toBe("rgb(128,128,128)");
    expect(mixHex("#000000", 2, "#ffffff")).toBe("rgb(0,0,0)");
    expect(mixHex("invalid", 0.12, "#ffffff")).toBe("#ffffff");
    expect(contrastText("#fff")).toBe("#000000");
    expect(contrastText("#000")).toBe("#ffffff");
  });
});
