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
const blend = (rgba, ground) => {
  const [r, g, b, a] = rgba.match(/[\d.]+/g).map(Number);
  const base = [1, 3, 5].map((i) => parseInt(ground.slice(i, i + 2), 16));
  return `#${[r, g, b].map((c, i) => Math.round(c * a + base[i] * (1 - a)).toString(16).padStart(2, "0")).join("")}`;
};

describe("surface ladder on the phone", () => {
  it("draws the one fill a clear step off the light pane", () => {
    expect(palettes.light.bg).toBe(palettes.light.bgPane);
    expect(contrastRatio(palettes.light.fill, palettes.light.bgPane)).toBeGreaterThan(1.1);
    expect(contrastRatio(palettes.light.bgSide, palettes.light.bgPane)).toBeGreaterThan(1.05);
  });

  it("grounds the dark phone on the #1a1a1a pane, lifts the fill and raises floats above it", () => {
    expect(palettes.dark.bg).toBe(palettes.dark.bgPane);
    expect(palettes.dark.bg).toBe("#1a1a1a");
    expect(contrastRatio(palettes.dark.bgSide, palettes.dark.bg)).toBeGreaterThanOrEqual(1.07);
    expect(contrastRatio(palettes.dark.fill, palettes.dark.bg)).toBeGreaterThan(1.1);
    expect(contrastRatio(palettes.dark.raised, palettes.dark.fill)).toBeGreaterThan(1.04);
    expect(palettes.dark.bgElev).toBe("#2c2c2c");
  });
});

describe("contrast on every phone surface", () => {
  const SURFACES = ["bg", "fill", "raised", "card", "field", "bgElev", "bgInput", "bgSide"];

  it.each(["light", "dark"])("keeps every text pair at 4.5:1 on every %s surface", (mode) => {
    const c = palettes[mode];
    for (const ground of SURFACES) {
      for (const ink of ["ink", "ink2", "successText", "warningText", "dangerText"]) {
        expect(contrastRatio(c[ink], c[ground]), `${ink} on ${ground}`).toBeGreaterThanOrEqual(4.5);
      }
    }
    for (const ground of ["bg", "fill", "raised", "bgSide"]) expect(contrastRatio(c.ink3, c[ground]), `ink3 on ${ground}`).toBeGreaterThanOrEqual(4.5);
  });

  it.each(["light", "dark"])("draws the %s focus ring at 3:1 or more on every ground and on the chosen fill", (mode) => {
    const c = palettes[mode];
    const ring = (ground) => blend(`rgba(${[1, 3, 5].map((i) => parseInt(c.ink.slice(i, i + 2), 16)).join(",")},0.6)`, ground);
    for (const ground of [...SURFACES, blend(c.selected, c.bg)]) {
      const solid = c[ground] ?? ground;
      expect(contrastRatio(ring(solid), solid), `ring on ${ground}`).toBeGreaterThanOrEqual(3);
    }
  });

  it.each(["light", "dark"])("keeps the off outline and the float edge at 3:1 in %s", (mode) => {
    const c = palettes[mode];
    for (const ground of ["bg", "bgElev"]) expect(contrastRatio(c.edge, c[ground]), `edge on ${ground}`).toBeGreaterThanOrEqual(3);
    expect(contrastRatio(c.ink3, c.fill), "field focus line on the fill").toBeGreaterThanOrEqual(3);
  });

  it.each(["light", "dark"])("tells chosen from hover and keeps the chosen row readable in %s", (mode) => {
    const c = palettes[mode];
    const chosen = blend(c.selected, c.bg);
    const hover = blend(c.hover, c.bg);
    expect(contrastRatio(chosen, c.bg)).toBeGreaterThanOrEqual(1.15);
    expect(contrastRatio(chosen, hover)).toBeGreaterThan(1.05);
    for (const ink of ["ink", "ink2", "dangerText", "warningText"]) expect(contrastRatio(c[ink], chosen), `${ink} on chosen`).toBeGreaterThanOrEqual(4.5);
  });

  it.each(["light", "dark"])("labels the %s primary on the accent and on its pressed step at 4.5:1", (mode) => {
    const c = palettes[mode];
    expect(contrastRatio(c.bgPane, c.accent)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(c.bgPane, mixHex(c.accent, 0.78, c.bgPane).replace(/rgb\((\d+),(\d+),(\d+)\)/, (_, r, g, b) => `#${[r, g, b].map((v) => Number(v).toString(16).padStart(2, "0")).join("")}`))).toBeGreaterThanOrEqual(4.5);
  });
});
