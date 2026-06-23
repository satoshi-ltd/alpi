import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { useUsageDaily, useWorkgroupUsageDaily } from "./useUsage.js";

beforeEach(() => {
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
});
