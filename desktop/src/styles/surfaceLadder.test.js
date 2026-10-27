import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { ladderDirection, palettes } from "../../../common/tokens.mjs";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");
const TOKENS = read("styles/tokens.css");
const rule = (css, selector) => css.match(new RegExp(`(?:^|\\n)${selector.replace(/[.\[\]="()]/g, "\\$&")}\\s*\\{([^{}]*)\\}`))?.[1] ?? "";
const luminance = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

describe("surface ladder", () => {
  it("writes the direction per mode and the palettes obey it", () => {
    expect(ladderDirection).toEqual({ light: "descends", dark: "ascends" });
    expect(luminance(palettes.light.card)).toBeLessThan(luminance(palettes.light.bgPane));
    expect(luminance(palettes.light.field)).toBeLessThan(luminance(palettes.light.card));
    expect(luminance(palettes.dark.bgElev)).toBeGreaterThan(luminance(palettes.dark.bgPane));
    expect(luminance(palettes.dark.field)).toBeGreaterThan(luminance(palettes.dark.card));
    expect(TOKENS).toMatch(/Ladder: light surfaces descend/);
  });

  it("mirrors the card, field and elev values in tokens.css for both modes", () => {
    const declared = (name) => [...TOKENS.matchAll(new RegExp(`--${name}:\\s*(#[0-9a-f]{6});`, "g"))].map((m) => m[1]);
    expect(declared("card")).toEqual([palettes.light.card, palettes.dark.card, palettes.dark.card]);
    expect(declared("field")).toEqual([palettes.light.field, palettes.dark.field, palettes.dark.field]);
    expect(declared("bg-elev")).toEqual([palettes.light.bgElev, palettes.dark.bgElev, palettes.dark.bgElev]);
  });

  it("draws every well on the elevated surface, keeps that fill on focus and leaves the field tone to disabled wells", () => {
    expect(TOKENS).toMatch(/--well:\s*var\(--bg-elev\);/);
    expect(TOKENS).toMatch(/--well-focus:\s*var\(--bg-elev\);/);
    expect(TOKENS).toMatch(/--well-off:\s*var\(--field\);/);
  });

  it.each([
    ["features/settings/Settings.module.css", ".adminBanner"],
    ["features/settings/Settings.module.css", ".lockedValue"],
    ["features/settings/Settings.module.css", ".linkPill"],
    ["features/Welcome.module.css", ".card"],
  ])("paints %s %s as a card", (file, selector) => {
    const body = rule(read(file), selector);
    if (body) expect(body).toMatch(/background:\s*var\(--card\)/);
    expect(read(file)).not.toMatch(new RegExp(`\\${selector}\\s*\\{[^}]*--bg-side`));
  });

  it("keeps settings cards off the side-panel tone", () => {
    expect(read("features/settings/Settings.module.css")).not.toMatch(/background:\s*var\(--bg-side\)/);
  });
});
