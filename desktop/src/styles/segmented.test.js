import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const CSS = readFileSync(join(import.meta.dirname, "design-system.css"), "utf8");
const WORKGROUPS = readFileSync(join(import.meta.dirname, "..", "pages", "WorkgroupsView.jsx"), "utf8");

function rule(selector) {
  const at = CSS.indexOf(`${selector} {`);
  expect(at, selector).toBeGreaterThan(-1);
  return CSS.slice(at, CSS.indexOf("}", at));
}

describe("segmented control", () => {
  it("raises the chosen segment as a raised cell, never a black one", () => {
    const pressed = rule('.ds-seg > button[aria-pressed="true"],\n.ds-seg > button.is-on');
    expect(pressed).toMatch(/background:\s*var\(--raised\)/);
    expect(pressed).toMatch(/color:\s*var\(--ink\)/);
    expect(pressed).toMatch(/box-shadow:\s*var\(--shadow-cell\)/);
    expect(pressed).not.toMatch(/var\(--accent\)/);
  });

  it("edges the chosen cell in dark, where raised and fill sit too close, and sets it in semibold so the cue is not colour alone", () => {
    const tokens = readFileSync(join(import.meta.dirname, "tokens.css"), "utf8");
    const cells = [...tokens.matchAll(/--shadow-cell:\s*([^;]+);/g)].map((m) => m[1]);
    expect(cells).toHaveLength(3);
    for (const dark of cells.slice(1)) expect(dark).toMatch(/^0 0 0 1px rgba\(237, 237, 237, \.16\)/);
    expect(rule('.ds-seg > button[aria-pressed="true"],\n.ds-seg > button.is-on')).toMatch(/font-weight:\s*var\(--fw-semibold\)/);
  });

  it("sets the track and its cells as pills on the fill", () => {
    expect(rule(".ds-seg")).toMatch(/border-radius:\s*var\(--r-pill\)/);
    expect(rule(".ds-seg")).toMatch(/padding:\s*var\(--nest-inset\)/);
    expect(rule(".ds-seg > button")).toMatch(/border-radius:\s*var\(--r-pill\)/);
  });

  it("hovers a cell with the hover fill, presses it instantly with the pressed fill", () => {
    expect(rule(".ds-seg > button:not(:disabled):hover")).toMatch(/background:\s*var\(--hover\)/);
    expect(rule(".ds-seg > button:not(:disabled):active")).toMatch(/background:\s*var\(--pressed\);\s*transition:\s*none/);
    expect(rule(".ds-seg > button:disabled")).toMatch(/opacity:\s*var\(--alpha-disabled\)/);
  });

  it("keeps the rest quiet on the fill track", () => {
    expect(rule(".ds-seg")).toMatch(/background:\s*var\(--fill\)/);
    expect(rule(".ds-seg > button")).toMatch(/color:\s*var\(--ink-2\)/);
  });

  it("is what the workgroup filters use, with aria-pressed carrying the state", () => {
    expect(WORKGROUPS).toMatch(/className="ds-seg"/);
    expect(WORKGROUPS).toMatch(/aria-pressed=\{filter === item\.id\}/);
    expect(WORKGROUPS).not.toMatch(/filterActive/);
  });
});
