import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");
const rule = (css, selector) => css.match(new RegExp(`(?:^|\\n)${selector.replace(/[.\[\]"=:]/g, "\\$&")}\\s*\\{([^{}]*)\\}`))[1];

describe("control boundaries", () => {
  it("draws unchecked radios and checkboxes on --edge", () => {
    const css = read("styles/design-system.css");
    for (const selector of [".ds-radio", ".ds-checkbox"]) {
      expect(rule(css, selector)).toMatch(/border:\s*1\.5px solid var\(--edge\)/);
    }
  });

  it.each([
    ["primitives/TasksButton.module.css"],
    ["features/ScheduleModal.module.css"],
    ["features/SkillsModal.module.css"],
    ["primitives/icons.jsx"],
  ])("%s keeps control borders off --ink-4", (file) => {
    const src = read(file);
    expect(src).toMatch(/solid var\(--edge\)/);
    expect(src).not.toMatch(/border[^;\n]*var\(--ink-4\)/);
  });

  it("draws decorative hash glyphs in --ink-3", () => {
    expect(rule(read("styles/design-system.css"), ".ds-chat-header .title-row .ds-hash, .hash")).toMatch(/color:\s*var\(--ink-3\)/);
    expect(rule(read("pages/ChatPane.module.css"), ".emptyHash")).toMatch(/color:\s*var\(--ink-3\)/);
  });

  it("sets secondary failure text at the meta size", () => {
    expect(rule(read("primitives/LoadFailed.module.css"), ".detail")).toMatch(/font-size:\s*var\(--text-meta\)/);
    expect(rule(read("pages/WorkgroupsView.module.css"), ".statusNote")).toMatch(/font-size:\s*var\(--text-meta\)/);
  });

  it("rings an invalid field in danger, focused or not", () => {
    const css = read("styles/design-system.css");
    expect(css).toMatch(/\.ds-field\[aria-invalid="true"\][^{]*\{\s*box-shadow:\s*inset 0 0 0 1px var\(--c-danger\);/);
    expect(css).toMatch(/\.ds-field\[aria-invalid="true"\]:focus/);
  });
});
