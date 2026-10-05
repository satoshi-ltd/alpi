import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { phaseGround, PHASE_GROUND } from "../../../common/pipelinePhases.mjs";

const css = readFileSync(join(import.meta.dirname, "PipelineStages.module.css"), "utf8");
const groundOf = (state) => css.match(new RegExp(`\\.chip\\[data-state="${state}"\\]\\s*\\{([^}]*)\\}`))?.[1] ?? "";

describe("the pipeline chip's ground", () => {
  it("tints only the terminal states, at the percentages common/ declares", () => {
    for (const [state, [token, alpha]] of Object.entries(PHASE_GROUND)) {
      expect(groundOf(state)).toContain(`color-mix(in srgb, var(--c-${token}) ${Math.round(alpha * 100)}%, transparent)`);
    }
  });

  it("leaves running and pending on the neutral grounds, so only the folding object says it works", () => {
    expect(PHASE_GROUND.current).toBeUndefined();
    expect(groundOf("current")).toContain("var(--selected)");
    expect(css).not.toMatch(/data-state="current"\]\s*\{[^}]*c-(success|warning|danger)/);
    expect(css).not.toContain("--c-warning");
  });
});


describe("native phase grounds", () => {
  it("uses each theme's status palette with the specified opacity", () => {
    expect(phaseGround("completed", { success: "#3fb37a" })).toBe("rgba(63, 179, 122, 0.18)");
    expect(phaseGround("blocked", { danger: "#c14545" })).toBe("rgba(193, 69, 69, 0.14)");
    expect(phaseGround("completed", { success: "#7fba89" })).toBe("rgba(127, 186, 137, 0.18)");
    expect(phaseGround("blocked", { danger: "#d4877c" })).toBe("rgba(212, 135, 124, 0.14)");
    expect(phaseGround("completed", { success: "#0a0" })).toBe("rgba(0, 170, 0, 0.18)");
  });

  it("keeps nonterminal phases neutral and falls back for missing status colours", () => {
    for (const state of ["current", "pending", "skipped", "unknown"]) {
      expect(phaseGround(state, { success: "#3fb37a" })).toBeNull();
    }
    expect(phaseGround("completed", {})).toBeNull();
    expect(phaseGround("blocked", { danger: "invalid" })).toBeNull();
  });
});
