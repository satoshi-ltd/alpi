import { describe, it, expect } from "vitest";
import { dateBucket, groupByDate } from "./time.js";

const NOW = new Date(2026, 5, 17, 12, 0, 0).getTime();
const DAY = 86400000;
const sec = (ms) => Math.floor(ms / 1000);

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
