import { describe, expect, it } from "vitest";
import { fuzzyMatch, splitByRanges } from "./fuzzy.js";

describe("fuzzyMatch", () => {
  it("prefers a contiguous hit at a word start", () => {
    const start = fuzzyMatch("Deploy checklist", "dep");
    const inner = fuzzyMatch("Summarize yesterday's deploys", "dep");
    expect(start.ranges).toEqual([[0, 3]]);
    expect(inner.ranges).toEqual([[22, 25]]);
    expect(start.score).toBeGreaterThan(inner.score);
  });

  it("falls back to an in-order subsequence below any substring hit", () => {
    const sub = fuzzyMatch("New workgroup", "nwg");
    expect(sub.ranges).toEqual([[0, 1], [2, 3], [8, 9]]);
    expect(sub.score).toBeLessThan(fuzzyMatch("Snow wagon", "wag").score);
  });

  it("rejects when a character is missing and matches everything on an empty query", () => {
    expect(fuzzyMatch("Tools", "xyz")).toBeNull();
    expect(fuzzyMatch("Tools", "  ")).toEqual({ score: 0, ranges: [] });
  });
});

describe("splitByRanges", () => {
  it("marks the hit slices", () => {
    expect(splitByRanges("Staging deploy", [[8, 11]])).toEqual([
      { text: "Staging ", hit: false },
      { text: "dep", hit: true },
      { text: "loy", hit: false },
    ]);
  });
});
