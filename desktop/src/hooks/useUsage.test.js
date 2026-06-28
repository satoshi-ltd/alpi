import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { _clearUsageCache, useUsageDaily, useWorkgroupUsageDaily } from "./useUsage.js";

beforeEach(() => {
  _clearUsageCache();
  invoke.mockReset();
});

describe("usage hooks", () => {
  it("routes profile usage to the selected daemon and reports loading", async () => {
    let resolve;
    invoke.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    const { result } = renderHook(() => useUsageDaily("doc", "remote-a"));

    await waitFor(() => expect(result.current.loading).toBe(true));
    expect(invoke).toHaveBeenCalledWith("usage_daily", {
      profile: "doc",
      connectionId: "remote-a",
    });

    resolve({ days: [], priceOut: 0 });
    await waitFor(() => expect(result.current.loading).toBe(false));
  });

  it("routes workgroup usage to the selected daemon", async () => {
    invoke.mockResolvedValueOnce({ days: [] });
    renderHook(() => useWorkgroupUsageDaily("mira", "wg-1", "remote-b"));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("workgroup_usage_daily", {
        profile: "mira",
        wgId: "wg-1",
        connectionId: "remote-b",
      });
    });
  });

  it("serves cached usage immediately while refreshing in the background", async () => {
    invoke
      .mockResolvedValueOnce({ days: [{ iso: "2026-06-28", tokIn: 1, tokOut: 2, cost: 0.01 }], priceOut: 1 })
      .mockResolvedValueOnce({ days: [{ iso: "2026-06-28", tokIn: 3, tokOut: 4, cost: 0.02 }], priceOut: 2 });
    const first = renderHook(() => useUsageDaily("doc", "remote-a"));
    await waitFor(() => expect(first.result.current.days[0].tokIn).toBe(1));
    first.unmount();

    const second = renderHook(() => useUsageDaily("doc", "remote-a"));
    expect(second.result.current.days[0].tokIn).toBe(1);
    expect(second.result.current.loading).toBe(true);
    await waitFor(() => expect(second.result.current.days[0].tokIn).toBe(3));
  });
});
