import { describe, it, expect, vi, afterEach } from "vitest";
import { scheduleSummary, formatLastRun } from "./scheduleFormat.js";

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

describe("formatLastRun", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 'never run' without an execution status (cron anchor is not a run)", () => {
    expect(formatLastRun(null, undefined)).toBe("never run");
    expect(formatLastRun("2026-07-02T10:00:00Z", undefined)).toBe("never run");
    expect(formatLastRun("2026-07-02T10:00:00Z", null)).toBe("never run");
    expect(formatLastRun("not-a-date", "ok")).toBe("never run");
  });

  it("formats a successful run and flags a failed one", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-02T12:00:00Z"));
    expect(formatLastRun("2026-07-02T10:00:00Z", "ok")).toBe("ran 2h ago");
    expect(formatLastRun("2026-07-02T11:59:30Z", "ok")).toBe("ran just now");
    expect(formatLastRun("2026-07-02T10:00:00Z", "error")).toBe("last run failed · 2h ago");
  });
});
