import { describe, expect, it } from "vitest";
import { COST_CASES, SCHEDULE_CASES } from "../../../common/clientPresentation.fixtures.mjs";
import { formatCostLine } from "../../../common/format.mjs";
import { scheduleSummary } from "./scheduleFormat.js";
import { modelLabel } from "./modelLabel.js";
import { modelLabel as sharedModelLabel } from "../../../common/modelLabel.mjs";

describe("shared presentation contract", () => {
  it.each(COST_CASES)("formats cost %j as %s", (input, expected) => {
    expect(formatCostLine(input)).toBe(expected);
  });
  it.each(SCHEDULE_CASES)("formats schedule %j as %s", (input, expected) => {
    expect(scheduleSummary(input)).toBe(expected);
  });
  it("uses the canonical model label implementation", () => {
    expect(modelLabel).toBe(sharedModelLabel);
  });
});
