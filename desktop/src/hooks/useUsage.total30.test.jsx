import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useUsageDaily } from "./useUsage.js";

describe("useUsageDaily with a prefetched snapshot section", () => {
  it("exposes total30 from the snapshot payload without fetching", () => {
    const prefetched = {
      days: [{ iso: "2026-07-23", tokIn: 1, tokOut: 1, cost: 0.1 }],
      priceOut: 2.1,
      total30: { spanDays: 30, cost: 4.2, tokIn: 30, tokOut: 9 },
    };
    const { result } = renderHook(() => useUsageDaily("pulse", null, prefetched));
    expect(result.current.total30).toEqual(prefetched.total30);
    expect(result.current.loading).toBe(false);
  });

  it("returns total30 null against older daemons", () => {
    const prefetched = { days: [], priceOut: 2.1 };
    const { result } = renderHook(() => useUsageDaily("pulse", null, prefetched));
    expect(result.current.total30).toBeNull();
  });
});
