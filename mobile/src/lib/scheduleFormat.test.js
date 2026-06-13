import { describe, it, expect } from "vitest";
import { scheduleSummary } from "./scheduleFormat.js";

describe("scheduleSummary", () => {
  it.each([
    [null, "?"],
    [undefined, "?"],
    [{}, "?"],
    [{ kind: "cron", expression: "0 9 * * 1" }, "0 9 * * 1"],
    [{ kind: "cron" }, "?"],
    [{ kind: "once", run_at: "2026-12-31T23:59" }, "once 2026-12-31T23:59"],
    [{ kind: "once" }, "once ?"],
    [{ kind: "inactivity", after_hours: 24 }, "after 24h"],
    [{ kind: "inactivity" }, "after ?h"],
    [{ kind: "weird-future-kind" }, "weird-future-kind"],
  ])("%j → %s", (job, expected) => {
    expect(scheduleSummary(job)).toBe(expected);
  });
});
