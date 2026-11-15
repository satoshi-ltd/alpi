import { describe, expect, it } from "vitest";

import { focusRing, palettes, stateFills } from "../../../common/tokens.mjs";

const channels = (colour) => {
  const rgba = colour.match(/^rgba\(([^)]+)\)$/);
  if (rgba) return rgba[1].split(",").slice(0, 3).map(Number);
  return [1, 3, 5].map((i) => parseInt(colour.slice(i, i + 2), 16));
};
const alphaOf = (colour) => (colour.startsWith("rgba(") ? Number(colour.slice(5, -1).split(",")[3]) : 1);
const over = (colour, ground, amount = alphaOf(colour)) => {
  const fg = channels(colour);
  const bg = channels(ground);
  return `#${fg.map((c, i) => Math.round(c * amount + bg[i] * (1 - amount)).toString(16).padStart(2, "0")).join("")}`;
};
const luminance = (hex) => {
  const [r, g, b] = channels(hex).map((v) => v / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

const MODES = ["light", "dark"];
const well = (p) => p.fill;
const ring = (p, ground) => over(p.ink, ground, focusRing.alpha);
const fill = (p, ground, amount) => over(p.ink, ground, amount);

describe.each(MODES)("the %s surfaces", (mode) => {
  const p = palettes[mode];
  const stateFill = stateFills[mode];

  it("tells the sidebar from the content by tone alone", () => {
    expect(ratio(p.bgSide, p.bgPane)).toBeGreaterThanOrEqual(1.07);
    expect(ratio(well(p, mode), p.bgPane)).toBeGreaterThanOrEqual(1.05);
    expect(ratio(p.ink2, p.bgSide)).toBeGreaterThanOrEqual(4.5);
    expect(ratio(p.ink3, well(p, mode))).toBeGreaterThanOrEqual(4.5);
  });

  it.each(["bgPane", "bgSide", "bgElev", "card", "field"])("keeps every text ink at 4.5:1 on %s", (ground) => {
    for (const ink of ["ink", "ink2", "ink3", "successText", "warningText", "dangerText"]) {
      if (ground === "field" && ink !== "ink" && ink !== "ink2") continue;
      expect(ratio(p[ink], p[ground]), `${ink} on ${ground}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("holds the focus ring at 3:1 on every ground it can land on", () => {
    for (const ground of [p.bgPane, p.bgSide, p.bgElev, well(p, mode), fill(p, p.bgSide, stateFill.selected), fill(p, p.bgElev, stateFill.selected)]) {
      expect(ratio(ring(p, ground), ground), ground).toBeGreaterThanOrEqual(3);
    }
  });
});

describe.each(MODES)("the %s controls", (mode) => {
  const p = palettes[mode];

  it("labels the primary at 4.5:1 at rest, hovered and pressed", () => {
    for (const amount of [1, 0.88, 0.8]) expect(ratio(p.bgPane, over(p.accent, p.bgPane, amount))).toBeGreaterThanOrEqual(4.5);
  });

  it("labels the secondary at 4.5:1 on its pressed 16 % fill", () => {
    expect(ratio(p.ink, fill(p, p.bgPane, 0.16))).toBeGreaterThanOrEqual(4.5);
  });

  it("keeps the off outline, the checked fill and the error ring at 3:1", () => {
    expect(ratio(p.edge, p.bgPane)).toBeGreaterThanOrEqual(3);
    expect(ratio(p.ink, p.bgPane)).toBeGreaterThanOrEqual(3);
    expect(ratio(p.dangerText, well(p, mode))).toBeGreaterThanOrEqual(3);
  });

  it("writes the tooltip at 4.5:1 on its ink fill", () => {
    expect(ratio(p.bgPane, p.ink)).toBeGreaterThanOrEqual(4.5);
  });
});

describe.each(MODES)("the %s lists", (mode) => {
  const p = palettes[mode];
  const stateFill = stateFills[mode];
  const chosen = fill(p, p.bgSide, stateFill.selected);
  const hover = fill(p, p.bgSide, stateFill.hover);

  it("declares the chosen and hover fills at the mode's state alphas of ink", () => {
    expect(alphaOf(p.selected)).toBe(stateFill.selected);
    expect(alphaOf(p.hover)).toBe(stateFill.hover);
    expect(channels(p.selected)).toEqual(channels(p.ink));
  });

  it("parts chosen from hover from rest", () => {
    expect(ratio(chosen, p.bgSide)).toBeGreaterThanOrEqual(1.15);
    expect(ratio(hover, p.bgSide)).toBeGreaterThanOrEqual(1.05);
    expect(ratio(chosen, hover)).toBeGreaterThanOrEqual(1.05);
  });

  it("keeps the chosen name and the stepped trailing text at 4.5:1 on the chosen fill", () => {
    expect(ratio(p.ink, chosen)).toBeGreaterThanOrEqual(4.5);
    expect(ratio(p.ink2, chosen)).toBeGreaterThanOrEqual(4.5);
    expect(ratio(p.warningText, hover)).toBeGreaterThanOrEqual(4.5);
    expect(ratio(p.dangerText, chosen)).toBeGreaterThanOrEqual(4.5);
  });

  it("keeps a highlighted menu item and a danger item readable on the float", () => {
    expect(ratio(p.ink, fill(p, p.bgElev, stateFill.selected))).toBeGreaterThanOrEqual(4.5);
    expect(ratio(p.dangerText, p.bgElev)).toBeGreaterThanOrEqual(4.5);
  });
});
