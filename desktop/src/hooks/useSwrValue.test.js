import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

vi.mock("../lib/daemon-bus.js", () => ({
  subscribeDaemonEvent: () => () => {},
}));

import { createSwrCache, _clearAllSwrCaches } from "../lib/swr-cache.js";
import { useSwrValue } from "./useSwrValue.js";

beforeEach(() => {
  _clearAllSwrCaches();
});

describe("useSwrValue", () => {
  it("serves cached data synchronously on remount while revalidating", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(["v1"]).mockResolvedValueOnce(["v2"]);
    const cache = createSwrCache({ fetcher });
    const first = renderHook(() => useSwrValue(cache, "c1|a", {}));
    await waitFor(() => expect(first.result.current.data).toEqual(["v1"]));
    first.unmount();

    const second = renderHook(() => useSwrValue(cache, "c1|a", {}));
    expect(second.result.current.data).toEqual(["v1"]);
    await waitFor(() => expect(second.result.current.data).toEqual(["v2"]));
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("defer holds the fetch and reports loading; lifting it fetches", async () => {
    const fetcher = vi.fn().mockResolvedValue(["v"]);
    const cache = createSwrCache({ fetcher });
    const { result, rerender } = renderHook(
      ({ defer }) => useSwrValue(cache, "c1|a", {}, { defer }),
      { initialProps: { defer: true } },
    );
    expect(result.current.loading).toBe(true);
    expect(fetcher).not.toHaveBeenCalled();

    rerender({ defer: false });
    await waitFor(() => expect(result.current.data).toEqual(["v"]));
  });

  it("prefetched mode seeds the cache without fetching", async () => {
    const fetcher = vi.fn();
    const cache = createSwrCache({ fetcher });
    const { result } = renderHook(() =>
      useSwrValue(cache, "c1|a", {}, { prefetched: ["seeded"] }),
    );
    expect(result.current.data).toEqual(["seeded"]);
    expect(result.current.loading).toBe(false);
    await Promise.resolve();
    expect(fetcher).not.toHaveBeenCalled();
    expect(cache.get("c1|a")).toEqual(["seeded"]);
  });

  it("enabled=false stays idle", async () => {
    const fetcher = vi.fn();
    const cache = createSwrCache({ fetcher });
    const { result } = renderHook(() => useSwrValue(cache, "c1|a", {}, { enabled: false }));
    await Promise.resolve();
    expect(fetcher).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
    expect(result.current.loading).toBe(false);
  });

  it("switching keys never shows the previous key's data", async () => {
    let resolveB;
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(["from-a"])
      .mockImplementationOnce(() => new Promise((r) => { resolveB = r; }));
    const cache = createSwrCache({ fetcher });
    const { result, rerender } = renderHook(
      ({ k }) => useSwrValue(cache, k, {}),
      { initialProps: { k: "c1|a" } },
    );
    await waitFor(() => expect(result.current.data).toEqual(["from-a"]));

    rerender({ k: "c1|b" });
    expect(result.current.data).toBeUndefined();
    expect(result.current.loading).toBe(true);
    resolveB(["from-b"]);
    await waitFor(() => expect(result.current.data).toEqual(["from-b"]));
  });
});
