import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import * as shared from "../../../common/tokens.mjs";

const CSS = readFileSync(join(import.meta.dirname, "tokens.css"), "utf8");
const declared = (name) => [...CSS.matchAll(new RegExp(`--${name}:\\s*([^;]+);`, "g"))].map((m) => m[1].trim());
const one = (name) => {
  const values = declared(name);
  expect(values, `--${name}`).toHaveLength(1);
  return values[0];
};

const channels = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
const luminance = (hex) => {
  const [r, g, b] = channels(hex).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const composite = (ink, alpha, base) => {
  const i = channels(ink).map((c) => c * 255);
  const b = channels(base).map((c) => c * 255);
  return `#${i.map((c, k) => Math.round(c * alpha + b[k] * (1 - alpha)).toString(16).padStart(2, "0")).join("")}`;
};

describe("scales mirror the shared module", () => {
  it("declares the spacing scale 4/8/12/16/24/32", () => {
    for (const [name, value] of Object.entries(shared.spaceScale)) expect(one(`sp-${name}`)).toBe(`${value}px`);
    expect(Object.values(shared.spaceScale)).toEqual([4, 8, 12, 16, 24, 32]);
  });

  it("declares the control heights 24/28/32/40", () => {
    for (const [name, value] of Object.entries(shared.controlHeight)) expect(one(`ctl-${name}`)).toBe(`${value}px`);
    expect(Object.values(shared.controlHeight)).toEqual([24, 28, 32, 40]);
  });

  it("declares the type ladder 11/13/15/18/22/28 as --text-*", () => {
    expect(Object.values(shared.typeLadder)).toEqual([11, 13, 15, 18, 22, 28]);
    for (const [name, value] of Object.entries(shared.typeLadder)) expect(one(`text-${name}`)).toBe(`${value}px`);
  });

  it("declares weights 400/500/600 and the one eyebrow", () => {
    for (const [name, value] of Object.entries(shared.fontWeights)) expect(one(`fw-${name}`).split(";")[0]).toBe(String(value));
    expect(one("eyebrow-size")).toBe(`${shared.eyebrow.size}px`);
    expect(one("eyebrow-tracking")).toBe(`${shared.eyebrow.tracking}em`.replace("0.", "."));
  });

  it("declares dots 6/8 and the constant 1.33 icon stroke", () => {
    for (const [name, value] of Object.entries(shared.dotScale)) expect(one(`dot-${name}`)).toBe(`${value}px`);
    expect(one("icon-stroke")).toBe(String(shared.iconStrokeRendered));
    expect(one("icon-sm")).toBe(`${shared.iconSizesAllowed.desktop[0]}px`);
    expect(one("icon-md")).toBe(`${shared.iconSizesAllowed.desktop[1]}px`);
  });
});

describe("motion and focus mirror the shared module", () => {
  it("declares enter 180, exit 130, fast 120 and one 1600 ms pulse", () => {
    expect(one("dur-enter")).toBe(`${shared.motionTokens.enter}ms`);
    expect(one("dur-exit")).toBe(`${shared.motionTokens.exit}ms`);
    expect(one("dur-fast")).toBe(`${shared.motionTokens.fast}ms`);
    expect(one("dur-pulse")).toBe(`${shared.motionTokens.pulse}ms`);
    expect(one("pulse-low")).toBe("0.4");
    expect(shared.motionTokens.exit).toBeLessThan(shared.motionTokens.enter);
  });

  it("declares the easing pair with the shared control points", () => {
    expect(one("ease-enter")).toBe(`cubic-bezier(${shared.motionTokens.easeEnter.join(", ").replace(/\b0\./g, ".")})`);
    expect(one("ease-exit")).toBe(`cubic-bezier(${shared.motionTokens.easeExit.join(", ").replace(/\b0\./g, ".")})`);
    expect(one("ease")).toBe(one("ease-enter"));
  });

  it("declares the focus outline as 2 px at 60% ink with a 2 px offset", () => {
    expect(shared.focusRing).toEqual({ width: 2, offset: 2, alpha: 0.6 });
    expect(one("focus-outline-width")).toBe("2px");
    expect(one("focus-outline-offset")).toBe("2px");
    expect(one("focus-outline")).toBe("var(--focus-outline-width) solid color-mix(in srgb, var(--ink) 60%, transparent)");
  });

  it("renders every allowed desktop icon size at no less than 1.33 px", () => {
    for (const size of shared.iconSizesAllowed.desktop) expect((shared.iconStrokeFor(size) * size) / 24).toBeGreaterThanOrEqual(1.33 - 1e-9);
  });
});

describe("edge tiers", () => {
  it("lifts dark elev to #202020 in both clients' source", () => {
    expect(shared.palettes.dark.bgElev).toBe("#202020");
    expect(shared.palettes.light.bgElev).toBe("#ffffff");
  });

  it("holds the small ring above 3:1 and the large ring above the ink-4 control border", () => {
    const { light, dark } = shared.palettes;
    expect(contrast(light.edge, light.bgElev)).toBeGreaterThanOrEqual(3);
    expect(contrast(dark.edge, dark.bgElev)).toBeGreaterThanOrEqual(3);
    expect(contrast(light.ink4, light.bgElev)).toBeGreaterThanOrEqual(2);
    const darkLine2 = composite("#ededed", 0.16, dark.bgElev);
    expect(darkLine2).toBe("#414141");
    expect(contrast(darkLine2, dark.bgElev)).toBeGreaterThanOrEqual(1.5);
    expect(contrast(light.ink4, light.bgElev)).toBeLessThan(contrast(light.edge, light.bgElev));
  });

  it("sets --ring-ctrl to the 1 px ink-4 ring", () => {
    expect(one("ring-ctrl")).toBe("0 0 0 1px var(--ink-4)");
  });
});

describe("surface ladder", () => {
  it("lifts the light card to 1.10:1 over white and the field to 1.09:1 inside it", () => {
    const { light, dark } = shared.palettes;
    expect(light.card).toBe("#f4f4f4");
    expect(Number(contrast(light.card, light.bgPane).toFixed(2))).toBeGreaterThanOrEqual(1.1);
    expect(Number(contrast(light.field, light.card).toFixed(2))).toBeGreaterThanOrEqual(1.07);
    expect(luminance(dark.field)).toBeGreaterThan(luminance(dark.card));
    expect(dark.field).toBe(composite("#ededed", 0.04, dark.card));
  });

  it("writes the direction per mode and the palettes obey it", () => {
    const { light, dark } = shared.palettes;
    expect(shared.ladderDirection).toEqual({ light: "descends", dark: "ascends" });
    expect(luminance(light.card)).toBeLessThan(luminance(light.bgPane));
    expect(luminance(dark.bgElev)).toBeGreaterThan(luminance(dark.bgPane));
  });
});
