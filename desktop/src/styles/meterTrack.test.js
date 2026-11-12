import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (rel) => readFileSync(join(import.meta.dirname, "..", rel), "utf8");
const rule = (css, selector) => {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const m = css.match(new RegExp(`(?:^|\\})\\s*${escaped}\\s*\\{([^}]*)\\}`));
  return m ? m[1] : "";
};

describe("meter track and fill", () => {
  const css = read("styles/design-system.css");

  it("draws every meter track on the visible line-2 tone, as the phone does", () => {
    expect(rule(css, ".ds-bar, .bar")).toMatch(/background:\s*var\(--line-2\)/);
    expect(rule(css, ".ds-meter .bar")).toMatch(/background:\s*var\(--line-2\)/);
    expect(rule(read("features/settings/Settings.module.css"), ".budgetBar")).toMatch(/background:\s*var\(--line-2\)/);
  });

  it("fills with the accent unless a caller passes its own colour", () => {
    expect(rule(css, ".ds-bar > i, .bar > i")).toMatch(/background:\s*var\(--c, var\(--accent\)\)/);
  });
});
