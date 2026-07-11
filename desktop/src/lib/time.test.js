import { describe, it, expect } from "vitest";
import { dateBucket, formatNextFire, groupByDate, lastRunShort, notificationTime, relativeTime } from "./time.js";

const NOW = new Date(2026, 5, 17, 12, 0, 0).getTime();
const DAY = 86400000;
const sec = (ms) => Math.floor(ms / 1000);
const CLOCK = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });

describe("dateBucket", () => {
  it("buckets by calendar proximity", () => {
    expect(dateBucket(sec(NOW), NOW)).toBe("Today");
    expect(dateBucket(sec(NOW - 2 * 3600000), NOW)).toBe("Today");
    expect(dateBucket(sec(NOW - DAY), NOW)).toBe("Yesterday");
    expect(dateBucket(sec(NOW - 3 * DAY), NOW)).toBe("This week");
    expect(dateBucket(sec(NOW - 10 * DAY), NOW)).toBe("This month");
    expect(dateBucket(sec(NOW - 60 * DAY), NOW)).toBe("Earlier");
  });
});

describe("groupByDate", () => {
  it("returns non-empty buckets newest-first, preserving row order", () => {
    const rows = [
      { id: "a", at: sec(NOW - 3600000) },
      { id: "b", at: sec(NOW - 2 * 3600000) },
      { id: "c", at: sec(NOW - DAY) },
      { id: "d", at: sec(NOW - 40 * DAY) },
    ];
    const groups = groupByDate(rows, (r) => r.at, NOW);
    expect(groups.map((g) => g.label)).toEqual(["Today", "Yesterday", "Earlier"]);
    expect(groups[0].rows.map((r) => r.id)).toEqual(["a", "b"]);
    expect(groups[1].rows.map((r) => r.id)).toEqual(["c"]);
  });

  it("skips empty buckets and tolerates empty input", () => {
    expect(groupByDate([], (r) => r.at, NOW)).toEqual([]);
    expect(groupByDate(null, (r) => r.at, NOW)).toEqual([]);
  });
});

describe("notificationTime", () => {
  it("shows the clock time for today's notifications", () => {
    const at = new Date(2026, 5, 17, 9, 5, 0).getTime();
    expect(notificationTime(sec(at), NOW)).toBe(CLOCK.format(new Date(at)));
  });

  it("falls back to relative age before today", () => {
    const yesterday = sec(NOW - DAY);
    expect(notificationTime(yesterday, NOW)).toBe(relativeTime(yesterday));
    expect(notificationTime(yesterday, NOW)).not.toContain(":");
  });

  it("returns empty for a missing timestamp", () => {
    expect(notificationTime(0, NOW)).toBe("");
  });
});

describe("formatNextFire", () => {
  it("shows a dash when there is no next fire", () => {
    expect(formatNextFire(null, NOW)).toBe("—");
  });

  it("labels today and tomorrow with the clock time", () => {
    const today = new Date(2026, 5, 17, 19, 0, 0);
    const tomorrow = new Date(2026, 5, 18, 7, 0, 0);
    expect(formatNextFire(today.toISOString(), NOW)).toBe(`today ${CLOCK.format(today)}`);
    expect(formatNextFire(tomorrow.toISOString(), NOW)).toBe(`tomorrow ${CLOCK.format(tomorrow)}`);
  });
});

describe("lastRunShort", () => {
  it("shows the clock time for a run earlier today", () => {
    const earlierToday = new Date(2026, 5, 17, 7, 0, 0);
    expect(lastRunShort(earlierToday.toISOString(), NOW)).toBe(CLOCK.format(earlierToday));
  });

  it("returns empty for a job that never ran", () => {
    expect(lastRunShort(null, NOW)).toBe("");
  });
});
