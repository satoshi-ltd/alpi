import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(import.meta.dirname, "TasksButton.module.css"), "utf8");

describe("tasks trigger pixels", () => {
  it("gives the phase trigger a label-wide box, not a control-sized square", () => {
    const rule = css.slice(css.indexOf(".phaseTrigger {"), css.indexOf("}", css.indexOf(".phaseTrigger {")));
    expect(rule).toMatch(/width:\s*var\(--pop-xs\)/);
    expect(rule).toMatch(/max-width:\s*var\(--pop-xs\)/);
  });
});
