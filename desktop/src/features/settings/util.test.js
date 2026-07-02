import { describe, it, expect, vi, afterEach } from "vitest";

import { formatLastRun } from "./util.js";

afterEach(() => {
  vi.useRealTimers();
});

describe("formatLastRun", () => {
  it("returns 'never run' without an execution status, even if last_run_at is set (cron anchor)", () => {
    expect(formatLastRun(null, undefined)).toBe("never run");
    expect(formatLastRun("2026-07-02T10:00:00Z", undefined)).toBe("never run");
    expect(formatLastRun("2026-07-02T10:00:00Z", null)).toBe("never run");
    expect(formatLastRun("not-a-date", "ok")).toBe("never run");
  });

  it("formats a successful run as a relative 'ran …' label", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-02T12:00:00Z"));
    expect(formatLastRun("2026-07-02T10:00:00Z", "ok")).toBe("ran 2h ago");
    expect(formatLastRun("2026-07-02T11:59:30Z", "ok")).toBe("ran just now");
  });

  it("flags a failed run distinctly", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-02T12:00:00Z"));
    expect(formatLastRun("2026-07-02T10:00:00Z", "error")).toBe("last run failed · 2h ago");
  });
});
