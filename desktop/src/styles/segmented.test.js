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
  it("fills the pressed segment with ink so the choice reads at a glance", () => {
    const pressed = rule('.ds-seg > button[aria-pressed="true"],\n.ds-seg > button.is-on');
    expect(pressed).toMatch(/background:\s*var\(--ink\)/);
    expect(pressed).toMatch(/color:\s*var\(--bg-pane\)/);
  });

  it("keeps the rest quiet on the hover track", () => {
    expect(rule(".ds-seg")).toMatch(/background:\s*var\(--selected\)/);
    expect(rule(".ds-seg > button")).toMatch(/color:\s*var\(--ink-3\)/);
  });

  it("is what the workgroup filters use, with aria-pressed carrying the state", () => {
    expect(WORKGROUPS).toMatch(/className="ds-seg"/);
    expect(WORKGROUPS).toMatch(/aria-pressed=\{filter === item\.id\}/);
    expect(WORKGROUPS).not.toMatch(/filterActive/);
  });
});
