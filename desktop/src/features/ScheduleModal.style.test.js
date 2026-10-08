import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const rule = (file, name) => {
  const css = readFileSync(join(import.meta.dirname, file), "utf8");
  const m = css.match(new RegExp(`\\.${name}\\s*\\{([^}]*)\\}`));
  return m ? m[1] : "";
};
const decl = (body, prop) => (body.match(new RegExp(`(?:^|;|\\s)${prop}:\\s*([^;]+);`)) || [])[1]?.trim();

describe("schedule list description", () => {
  it("wraps to two lines under the title, like a skill's blurb", () => {
    const job = rule("ScheduleModal.module.css", "jobDesc");
    const blurb = rule("SkillsModal.module.css", "rowBlurb");
    for (const prop of ["display", "-webkit-line-clamp", "-webkit-box-orient", "line-height", "overflow-wrap"]) {
      expect(decl(job, prop), prop).toBeDefined();
      expect(decl(job, prop), prop).toBe(decl(blurb, prop));
    }
    expect(decl(job, "-webkit-line-clamp")).toBe("2");
    expect(job).not.toMatch(/white-space:\s*nowrap/);
    expect(decl(rule("ScheduleModal.module.css", "jobRow"), "flex-direction")).toBe("column");
  });
});
