import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  useProfileDetail,
  invalidateProfileDetailCache,
  _clearProfileDetailCache,
} from "./useProfileDetail.js";

let daemonEventListener;

beforeEach(() => {
  _clearProfileDetailCache();
  vi.resetAllMocks();
  daemonEventListener = null;
  listen.mockImplementation(async (eventName, cb) => {
    if (eventName === "daemon-event") daemonEventListener = cb;
    return () => {};
  });
});

describe("useProfileDetail", () => {
  it("stays idle when name is null", async () => {
    const { result } = renderHook(() => useProfileDetail("conn-a", null));
    await Promise.resolve();
    expect(invoke).not.toHaveBeenCalled();
    expect(result.current.detail).toBeNull();
  });

  it("fetches host.profile.detail on mount and exposes it via `detail`", async () => {
    invoke.mockResolvedValueOnce({ peers: [{ id: "alice" }], models: ["a/b"] });
    const { result } = renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => {
      expect(result.current.detail).toEqual({ peers: [{ id: "alice" }], models: ["a/b"] });
    });
    expect(invoke).toHaveBeenCalledWith("profile_detail", { profile: "doc" });
  });

  it("hits the cache instead of refetching across remounts with same (conn, name)", async () => {
    invoke.mockResolvedValueOnce({ peers: ["alice"] });
    const h1 = renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => expect(h1.result.current.detail).toEqual({ peers: ["alice"] }));
    h1.unmount();
    const h2 = renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => expect(h2.result.current.detail).toEqual({ peers: ["alice"] }));
    expect(invoke).toHaveBeenCalledTimes(1);
  });

  it("scopes cache per (connectionId, name): same name on different daemons does NOT bleed", async () => {
    invoke
      .mockResolvedValueOnce({ peers: ["alice"] })   // conn-a
      .mockResolvedValueOnce({ peers: ["bob"] });     // conn-b
    const a = renderHook(() => useProfileDetail("conn-a", "doc"));
    const b = renderHook(() => useProfileDetail("conn-b", "doc"));
    await waitFor(() => {
      expect(a.result.current.detail).toEqual({ peers: ["alice"] });
      expect(b.result.current.detail).toEqual({ peers: ["bob"] });
    });
    expect(invoke).toHaveBeenCalledTimes(2);
  });

  it("config_changed for THIS (conn, profile) forces a refetch", async () => {
    invoke
      .mockResolvedValueOnce({ peers: ["alice"] })
      .mockResolvedValueOnce({ peers: ["alice", "bob"] });
    const { result } = renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => expect(result.current.detail).toEqual({ peers: ["alice"] }));
    await act(async () => {
      daemonEventListener({
        payload: {
          connection_id: "conn-a",
          frame: { event: "config_changed", data: { profile: "doc" } },
        },
      });
      await Promise.resolve();
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(result.current.detail).toEqual({ peers: ["alice", "bob"] });
    });
    expect(invoke).toHaveBeenCalledTimes(2);
  });

  it("config_changed for ANOTHER profile refetches THAT profile, not this one", async () => {
    invoke
      .mockResolvedValueOnce({ peers: ["alice"] })  // initial conn-a/doc
      .mockResolvedValueOnce({ peers: ["mirai-after"] }); // pre-warm conn-a/mirai
    renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(1));
    expect(invoke).toHaveBeenLastCalledWith("profile_detail", { profile: "doc" });
    daemonEventListener({
      payload: {
        connection_id: "conn-a",
        frame: { event: "config_changed", data: { profile: "mirai" } },
      },
    });
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(2));
    // Second call targets mirai, not doc — the watched (conn-a, doc) cache is untouched.
    expect(invoke).toHaveBeenLastCalledWith("profile_detail", { profile: "mirai" });
  });

  it("invalidateProfileDetailCache(prev) drops only that connection's entries", async () => {
    invoke
      .mockResolvedValueOnce({ peers: ["alice"] })
      .mockResolvedValueOnce({ peers: ["bob"] })
      .mockResolvedValueOnce({ peers: ["alice", "refetched"] });
    renderHook(() => useProfileDetail("conn-a", "doc"));
    renderHook(() => useProfileDetail("conn-b", "doc"));
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(2));

    invalidateProfileDetailCache("conn-a");
    // re-mounting for conn-a refetches; conn-b is untouched.
    renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(3));
    renderHook(() => useProfileDetail("conn-b", "doc"));
    await Promise.resolve();
    expect(invoke).toHaveBeenCalledTimes(3);  // conn-b still cached
  });

  it("refresh() forces a refetch and updates the cached detail", async () => {
    invoke
      .mockResolvedValueOnce({ peers: ["alice"] })
      .mockResolvedValueOnce({ peers: ["alice", "bob"] });
    const { result } = renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => expect(result.current.detail).toEqual({ peers: ["alice"] }));
    await act(async () => {
      await result.current.refresh();
    });
    await waitFor(() => {
      expect(result.current.detail).toEqual({ peers: ["alice", "bob"] });
    });
  });

  it("falls back to {} (not null) when invoke rejects, so consumers stop spinning", async () => {
    invoke.mockRejectedValueOnce(new Error("daemon offline"));
    const { result } = renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => expect(result.current.detail).toEqual({}));
  });

  it("coalesces a burst of config_changed events into ONE refetch (reconnect replay storm)", async () => {
    invoke
      .mockResolvedValueOnce({ peers: ["alice"] })
      .mockResolvedValue({ peers: ["after-burst"] });
    const { result } = renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => expect(result.current.detail).toEqual({ peers: ["alice"] }));

    await act(async () => {
      for (let i = 0; i < 25; i += 1) {
        daemonEventListener({
          payload: {
            connection_id: "conn-a",
            replay: true,
            frame: { event: "config_changed", data: { profile: "doc" } },
          },
        });
      }
    });
    await waitFor(() => {
      expect(result.current.detail).toEqual({ peers: ["after-burst"] });
    });
    // 1 initial + 1 debounced refetch — never 25.
    expect(invoke).toHaveBeenCalledTimes(2);
  });
});
