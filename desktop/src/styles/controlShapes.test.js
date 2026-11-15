import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const DS = readFileSync(join(import.meta.dirname, "design-system.css"), "utf8");
const rule = (selector) => {
  const at = DS.indexOf(`${selector} {`);
  expect(at, selector).toBeGreaterThan(-1);
  return DS.slice(at, DS.indexOf("}", at));
};

describe("checkbox and radio", () => {
  it("sets the box at the xs radius and the radio round, both outlined only when off", () => {
    expect(rule(".ds-checkbox")).toMatch(/border-radius:\s*var\(--r-xs\)/);
    expect(rule(".ds-checkbox")).toMatch(/border:\s*1\.5px solid var\(--edge\)/);
    expect(rule(".ds-radio")).toMatch(/border-radius:\s*50%/);
    expect(rule(".ds-radio")).toMatch(/border:\s*1\.5px solid var\(--edge\)/);
  });

  it("draws a checked box or radio as one ink fill with its mark cut out, no border", () => {
    expect(rule(".ds-checkbox.on")).toMatch(/border:\s*0;/);
    expect(rule(".ds-checkbox.on")).toMatch(/background:\s*var\(--ink\)/);
    expect(rule(".ds-checkbox")).toMatch(/color:\s*var\(--bg-pane\)/);
    expect(rule(".ds-radio.on")).toMatch(/border:\s*0;/);
    expect(rule(".ds-radio.on")).toMatch(/background:\s*var\(--ink\)/);
    expect(rule(".ds-radio-dot")).toMatch(/background:\s*var\(--bg-pane\)/);
  });
});

describe("the one state ladder", () => {
  it("steps the icon button and the action link through hover and an instant pressed fill, never when disabled", () => {
    for (const name of ["ds-iconbtn", "ds-alink"]) {
      expect(DS).toMatch(new RegExp(`\\.${name}:not\\(:disabled\\):hover`));
      expect(DS).toMatch(new RegExp(`\\.${name}:not\\(:disabled\\):active[^{]*\\{ background: var\\(--pressed\\); transition: none; \\}`));
    }
  });

  it("rests the connection pill on the selected fill with no ring", () => {
    expect(rule(".ds-conn-pill, .conn-pill")).toMatch(/background:\s*var\(--selected\)/);
    expect(rule(".ds-conn-pill, .conn-pill")).not.toMatch(/box-shadow/);
  });

  it("outlines only the tag that means off, with the edge ink", () => {
    expect(DS).toMatch(/\.ds-tag-out, \.tag-out \{ background: transparent; box-shadow: inset 0 0 0 1px var\(--edge\); \}/);
    expect(rule(".ds-tag, .tag")).toMatch(/border-radius:\s*var\(--r-pill\)/);
  });

  it("keeps key caps and inline code at the xs radius on a fill, no edge", () => {
    expect(rule(".ds-kbd, .kbd")).toMatch(/border-radius:\s*var\(--r-xs\)/);
    expect(rule(".ds-kbd, .kbd")).not.toMatch(/border:/);
    expect(rule(".alpi-md code")).toMatch(/border-radius:\s*var\(--r-xs\)/);
  });

  it("rounds code blocks, tables, figures and markers at the surface radius as fills", () => {
    for (const selector of [".alpi-md pre", ".alpi-md .md-table", ".alpi-md .md-code", ".alpi-md .md-figure img", ".ds-marker"]) {
      expect(rule(selector), selector).toMatch(/border-radius:\s*var\(--r-surface\)/);
      expect(rule(selector), selector).not.toMatch(/border:\s*[.\d]/);
    }
  });
});
