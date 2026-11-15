import { describe, expect, it } from "vitest";

import { ACCENT_HEXES } from "../../../common/accents.mjs";
import { toOklab } from "../../../common/shapes.mjs";
import { contrastRatio, NAME_MIN_CONTRAST, NAME_STEP, nameTone } from "../../../common/name.mjs";
import { palettes } from "../../../common/tokens.mjs";
import { MUTED_NAME, nameVars } from "../lib/nameVars.js";

const lightness = (hex) => toOklab(hex)[0];

describe("name tone", () => {
  it.each(ACCENT_HEXES)("sets %s's name darker than its mark in light and lighter in dark, readable on both", (accent) => {
    const light = nameTone(accent, palettes.light.bgPane);
    const dark = nameTone(accent, palettes.dark.bgPane);
    expect(lightness(light)).toBeLessThanOrEqual(lightness(accent) - NAME_STEP + 0.01);
    expect(lightness(dark)).toBeGreaterThanOrEqual(lightness(accent) + NAME_STEP - 0.01);
    expect(contrastRatio(light, palettes.light.bgPane)).toBeGreaterThanOrEqual(NAME_MIN_CONTRAST);
    expect(contrastRatio(dark, palettes.dark.bgPane)).toBeGreaterThanOrEqual(NAME_MIN_CONTRAST);
  });

  it("moves a dark accent further from its mark too, never towards the ground", () => {
    const navy = "#1f2a6b";
    expect(lightness(nameTone(navy, "#ffffff"))).toBeLessThan(lightness(navy));
  });

  it("answers nothing for a missing or malformed accent, so the name falls back to ink", () => {
    expect(nameTone(null, "#ffffff")).toBeNull();
    expect(nameTone("#12", "#ffffff")).toBeNull();
    expect(nameTone("#3899e2", "#fff")).toBe(nameTone("#3899e2", "#ffffff"));
    expect(nameVars(undefined)).toBeNull();
  });

  it("greys a paused name through the ink-3 token in both themes", () => {
    expect(MUTED_NAME).toEqual({ "--name-light": "var(--ink-3)", "--name-dark": "var(--ink-3)" });
  });
});
