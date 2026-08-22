import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { ACCENTS, ACCENT_HEXES } from "../../../common/accents.mjs";
import {
  alpha,
  dotSize,
  fontSizes,
  glyphSize,
  glyphSizeMd,
  lineHeights,
  palettes,
  radii,
  space,
} from "../../../common/tokens.mjs";

const CSS = readFileSync(join(import.meta.dirname, "tokens.css"), "utf8");

function blockBody(selector) {
  const head = selector.exec(CSS);
  if (!head) return "";
  const open = CSS.indexOf("{", head.index);
  let depth = 0;
  for (let i = open; i < CSS.length; i += 1) {
    if (CSS[i] === "{") depth += 1;
    else if (CSS[i] === "}") {
      depth -= 1;
      if (depth === 0) return CSS.slice(open + 1, i);
    }
  }
  return "";
}

const ROOT = blockBody(/^:root\s*\{/m);
const DARK_MEDIA = blockBody(/:root:not\(\[data-mode="light"\]\)\s*\{/);
const DARK_TOGGLE = blockBody(/^\[data-mode="dark"\]\s*\{/m);

function numberVars(body) {
  const out = {};
  for (const m of body.matchAll(/--([a-z0-9-]+):\s*(-?[0-9.]+)(px)?;/g)) out[m[1]] = Number(m[2]);
  return out;
}

const IS_COLOR = /^(#[0-9a-f]{3,8}|rgba?\([^)]*\))$/i;

const tokenKey = (cssName) =>
  cssName.replace(/^c-/, "").replace(/-([a-z0-9])/g, (_, c) => c.toUpperCase());

function colorVars(body) {
  const out = {};
  for (const m of body.matchAll(/--([a-z0-9-]+):\s*([^;]+);/g)) {
    const value = m[2].trim();
    if (IS_COLOR.test(value)) out[tokenKey(m[1])] = value;
  }
  return out;
}

function normalizeColor(raw) {
  const value = raw.trim().toLowerCase().replace(/\s+/g, "");
  const fn = value.match(/^rgba?\(([^)]*)\)$/);
  if (!fn) return value;
  return `rgba(${fn[1].split(",").map((n) => String(Number(n))).join(",")})`;
}

const cssPalettes = () => {
  const light = colorVars(ROOT);
  return { light, dark: { ...light, ...colorVars(DARK_TOGGLE) } };
};

function expectedNumbers() {
  const out = {};
  for (const [name, value] of Object.entries(fontSizes)) out[`fs-${name}`] = value;
  for (const [name, value] of Object.entries(lineHeights)) out[`lh-${name}`] = value;
  for (const [name, value] of Object.entries(space)) out[`space-${name.slice(1)}`] = value;
  for (const [name, value] of Object.entries(radii)) out[`r-${name}`] = value;
  for (const [name, value] of Object.entries(alpha)) out[`alpha-${name}`] = value;
  out["dot-size"] = dotSize;
  out["glyph-size"] = glyphSize;
  out["glyph-size-md"] = glyphSizeMd;
  return out;
}

describe("tokens.css against the shared token module", () => {
  it("parses the stylesheet at all, so a silent parse failure cannot fake a pass", () => {
    expect(ROOT.length).toBeGreaterThan(1000);
    expect(Object.keys(numberVars(ROOT)).length).toBeGreaterThanOrEqual(40);
    expect(Object.keys(expectedNumbers()).length).toBeGreaterThanOrEqual(35);
  });

  it("declares every shared numeric token with the shared value", () => {
    const declared = numberVars(ROOT);
    const missing = [];
    const mismatched = [];
    for (const [name, value] of Object.entries(expectedNumbers())) {
      if (declared[name] === undefined) missing.push(`--${name}`);
      else if (declared[name] !== value) mismatched.push(`--${name}: css ${declared[name]} vs shared ${value}`);
    }
    expect(missing).toEqual([]);
    expect(mismatched).toEqual([]);
  });

  it("reads both palettes at all, so a silent parse failure cannot fake a pass", () => {
    const { light, dark } = cssPalettes();
    expect(Object.keys(light).length).toBeGreaterThanOrEqual(17);
    expect(Object.keys(colorVars(DARK_TOGGLE)).length).toBeGreaterThanOrEqual(13);
    for (const probe of ["bg", "bgInput", "ink", "line", "accent", "success"]) {
      expect(light[probe], probe).toMatch(/^(#|rgba)/);
      expect(dark[probe], probe).toMatch(/^(#|rgba)/);
    }
    expect(dark.bg).not.toBe(light.bg);
  });

  it("takes the dark values from a block both desktop dark selectors agree on", () => {
    const media = colorVars(DARK_MEDIA);
    expect(Object.keys(media).length).toBeGreaterThanOrEqual(13);
    expect(media).toEqual(colorVars(DARK_TOGGLE));
  });

  it.each(["light", "dark"])("declares exactly the shared palette in %s", (mode) => {
    const css = cssPalettes()[mode];
    expect(Object.keys(css).sort()).toEqual(Object.keys(palettes[mode]).sort());
    const mismatched = [];
    for (const [key, value] of Object.entries(palettes[mode])) {
      if (normalizeColor(css[key]) !== normalizeColor(value)) {
        mismatched.push(`${key}: css ${normalizeColor(css[key])} vs shared ${normalizeColor(value)}`);
      }
    }
    expect(mismatched).toEqual([]);
  });
});

describe("accent palette", () => {
  it("offers twelve distinct six-digit hexes", () => {
    expect(ACCENT_HEXES).toHaveLength(12);
    expect(new Set(ACCENT_HEXES).size).toBe(12);
    for (const hex of ACCENT_HEXES) expect(hex).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("names every swatch once, so the picker can label what it renders", () => {
    const names = ACCENTS.map(([name]) => name);
    expect(new Set(names).size).toBe(names.length);
    for (const name of names) expect(name).toMatch(/^[a-z]+$/);
  });

  it("keeps the --accent default inside the choosable set", () => {
    const declared = colorVars(ROOT).accent;
    expect(ACCENT_HEXES).toContain(normalizeColor(declared));
  });
});
