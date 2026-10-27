import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const sheet = readFileSync(join(import.meta.dirname, "ActivityPanel.module.css"), "utf8");
const rule = (selector) => {
  const start = sheet.lastIndexOf(`\n${selector} {`) + 1;
  expect(start, `${selector} rule`).toBeGreaterThan(0);
  return sheet.slice(start, sheet.indexOf("}", start));
};

describe("Activity panel finish", () => {
  it("keeps section eyebrows sticky on an opaque ground, whole-pixel centred", () => {
    const head = rule(".sectionHead");
    expect(head).toMatch(/position:\s*sticky/);
    expect(head).toMatch(/top:\s*0/);
    expect(head).toMatch(/background:\s*var\(--bg-elev\)/);
    expect(head).toMatch(/height:\s*var\(--ctl-32\)/);
    expect(rule(".groupLabel")).toMatch(/line-height:\s*var\(--sp-16\)/);
  });

  it("gives job rows exactly 40 px and group heads and chips 32 and 24 px", () => {
    expect(rule(".row")).toMatch(/height:\s*var\(--ctl-40\)/);
    expect(rule(".groupHead")).toMatch(/height:\s*var\(--ctl-32\)/);
    expect(rule(".filter")).toMatch(/height:\s*var\(--ctl-24\)/);
  });

  it("stacks title and meta on two 16 px line boxes so the pair is 32 px in a 40 px row", () => {
    expect(rule(".title")).toMatch(/line-height:\s*var\(--sp-16\)/);
    expect(rule(".sub")).toMatch(/line-height:\s*var\(--sp-16\)/);
    expect(rule(".text")).not.toMatch(/gap:/);
  });

  it("draws a timed run on one 32 px line under a 24 px day heading", () => {
    expect(rule(".timedRow")).toMatch(/height:\s*var\(--ctl-32\)/);
    expect(rule(".dayHead")).toMatch(/height:\s*var\(--ctl-24\)/);
    expect(rule(".time")).toMatch(/font-family:\s*var\(--font-mono\)/);
    expect(rule(".timedMain:focus-visible")).toMatch(/outline-offset:\s*calc\(var\(--focus-outline-offset\) \* -1\)/);
  });

  it("keeps the filters on one line and reveals Open and Retry on hover and focus", () => {
    expect(rule(".filters")).toMatch(/flex-wrap:\s*nowrap/);
    expect(sheet).toMatch(/\.row\[data-reveal\]:hover \.actions,\s*\.row\[data-reveal\]:focus-within \.actions\s*\{\s*display:\s*flex/);
    expect(rule(".row[data-reveal] .actions")).toMatch(/display:\s*none/);
  });

  it("insets the focus ring on rows, group heads and chips like the menu rows", () => {
    for (const selector of [".filter:focus-visible", ".groupHead:focus-visible", "button.rowMain:focus-visible"]) {
      expect(rule(selector)).toMatch(/outline-offset:\s*calc\(var\(--focus-outline-offset\) \* -1\)/);
    }
  });

  it("animates the expand only when motion is allowed", () => {
    const at = sheet.indexOf("@media (prefers-reduced-motion: no-preference)");
    expect(at).toBeGreaterThanOrEqual(0);
    expect(sheet.slice(0, at)).not.toMatch(/animation:/);
  });

  it("uses tokens for every colour and size, flat paper edges, no blur or gradient", () => {
    expect(sheet).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(sheet).not.toMatch(/\brgba?\(|\bhsla?\(/);
    expect(sheet).not.toMatch(/blur\(|gradient\(|backdrop-filter/);
    expect(sheet).not.toMatch(/border-radius:\s+(?!var\(--r-xs\)|0)/);
    const px = [...sheet.matchAll(/:\s*[^;{]*?(\d+(?:\.\d+)?)px/g)].map((m) => m[0]);
    expect(px.filter((m) => !/(?:^|\s)(?:\.5|1)px$/.test(m))).toEqual([]);
  });

  it("keeps the dot-free layout whole-pixel: no fractional sizes", () => {
    expect(sheet).not.toMatch(/\d\.\d+(px|rem|em)/);
  });
});
