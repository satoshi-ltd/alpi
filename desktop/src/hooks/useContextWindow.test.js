import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";

import { useContextWindow } from "./useContextWindow.js";

beforeEach(() => {
  vi.resetAllMocks();
});

describe("useContextWindow", () => {
  it("resolves the real context window for a model", async () => {
    invoke.mockResolvedValue(1048576);
    const { result } = renderHook(() =>
      useContextWindow("forge", "openrouter/deepseek/deepseek-v4-flash"),
    );
    expect(result.current).toBe(200000);
    await waitFor(() => expect(result.current).toBe(1048576));
    expect(invoke).toHaveBeenCalledWith("resolve_ctx_window", {
      profile: "forge",
      model: "openrouter/deepseek/deepseek-v4-flash",
    });
  });

  it("falls back to 200k on error", async () => {
    invoke.mockRejectedValue(new Error("offline"));
    const { result } = renderHook(() => useContextWindow("forge", "x/y"));
    await waitFor(() => expect(result.current).toBe(200000));
  });

  it("does not call invoke without profile or model", () => {
    const { result } = renderHook(() => useContextWindow(null, null));
    expect(result.current).toBe(200000);
    expect(invoke).not.toHaveBeenCalled();
  });

  it("re-resolves when only the connection changes, same profile/model", async () => {
    invoke.mockImplementation(async (_cmd, args) =>
      args.connectionId === "B" ? 480000 : 240000,
    );
    const { result, rerender } = renderHook(
      ({ conn }) => useContextWindow("forge", "x/y", conn),
      { initialProps: { conn: "A" } },
    );
    await waitFor(() => expect(result.current).toBe(240000));
    rerender({ conn: "B" });
    await waitFor(() => expect(result.current).toBe(480000));
    expect(invoke).toHaveBeenCalledWith("resolve_ctx_window", {
      profile: "forge",
      model: "x/y",
      connectionId: "A",
    });
    expect(invoke).toHaveBeenCalledWith("resolve_ctx_window", {
      profile: "forge",
      model: "x/y",
      connectionId: "B",
    });
  });
});
