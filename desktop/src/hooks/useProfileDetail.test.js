import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  useProfileDetail,
  invalidateProfileDetailCache,
  _clearProfileDetailCache,
  _profileDetailInflightSinceKeys,
} from "./useProfileDetail.js";
import { _resetDaemonBus } from "../lib/daemon-bus.js";
import { _resetProfileEdits, applyEdits, beginEdit, confirmEdit } from "../lib/optimisticProfiles.js";

let daemonEventListener;

beforeEach(() => {
  _resetProfileEdits();
  _clearProfileDetailCache();
  _resetDaemonBus();
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
    expect(invoke).toHaveBeenCalledWith("profile_detail", { profile: "doc", connectionId: "conn-a" });
  });

  it("can force a fresh daemon fetch on mount and exposes its loading state", async () => {
    let resolve;
    invoke.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    const { result } = renderHook(() => (
      useProfileDetail("conn-a", "doc", { refreshOnMount: true })
    ));
    await waitFor(() => expect(result.current.loading).toBe(true));
    await act(async () => {
      resolve({ voice_id: "es-ES-AlvaroNeural" });
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
      expect(result.current.detail).toEqual({ voice_id: "es-ES-AlvaroNeural" });
    });
  });

  it("forwards connectionId to the profile_detail RPC so it hits the right daemon", async () => {
    invoke.mockResolvedValueOnce({ voice_id: "es-ES-AlvaroNeural" });
    renderHook(() => useProfileDetail("remote-a", "doc"));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("profile_detail", { profile: "doc", connectionId: "remote-a" });
    });
  });

  it("serves the cached detail synchronously on remount and revalidates in the background (SWR)", async () => {
    invoke
      .mockResolvedValueOnce({ peers: ["alice"] })
      .mockResolvedValueOnce({ peers: ["alice", "bob"] });
    const h1 = renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => expect(h1.result.current.detail).toEqual({ peers: ["alice"] }));
    h1.unmount();

    const h2 = renderHook(() => useProfileDetail("conn-a", "doc"));
    expect(h2.result.current.detail).toEqual({ peers: ["alice"] });
    await waitFor(() => expect(h2.result.current.detail).toEqual({ peers: ["alice", "bob"] }));
    expect(invoke).toHaveBeenCalledTimes(2);
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
    expect(invoke).toHaveBeenLastCalledWith("profile_detail", { profile: "doc", connectionId: "conn-a" });
    daemonEventListener({
      payload: {
        connection_id: "conn-a",
        frame: { event: "config_changed", data: { profile: "mirai" } },
      },
    });
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(2));
    // Second call targets mirai, not doc — the watched (conn-a, doc) cache is untouched.
    expect(invoke).toHaveBeenLastCalledWith("profile_detail", { profile: "mirai", connectionId: "conn-a" });
  });

  it("invalidateProfileDetailCache(prev) drops only that connection's entries", async () => {
    invoke
      .mockResolvedValueOnce({ peers: ["alice"] })
      .mockResolvedValueOnce({ peers: ["bob"] })
      .mockResolvedValueOnce({ peers: ["alice", "refetched"] })
      .mockResolvedValue({ peers: ["bob"] });
    renderHook(() => useProfileDetail("conn-a", "doc"));
    renderHook(() => useProfileDetail("conn-b", "doc"));
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(2));

    invalidateProfileDetailCache("conn-a");
    // conn-a lost its entry: nothing cached, the mount fetch is the only source.
    const a = renderHook(() => useProfileDetail("conn-a", "doc"));
    expect(a.result.current.detail).toBeNull();
    await waitFor(() => expect(a.result.current.detail).toEqual({ peers: ["alice", "refetched"] }));

    // conn-b survived: its cached detail is served synchronously (SWR revalidates behind it).
    const b = renderHook(() => useProfileDetail("conn-b", "doc"));
    expect(b.result.current.detail).toEqual({ peers: ["bob"] });
  });

  it("forgets each fetch's start clock once it settles or its connection is invalidated", async () => {
    let finishB;
    invoke
      .mockResolvedValueOnce({ peers: [] })
      .mockRejectedValueOnce(new Error("down"))
      .mockReturnValueOnce(new Promise((r) => { finishB = r; }))
      .mockReturnValueOnce(new Promise(() => {}));
    renderHook(() => useProfileDetail("conn-a", "doc"));
    renderHook(() => useProfileDetail("conn-a", "mirai"));
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(_profileDetailInflightSinceKeys()).toEqual([]));
    renderHook(() => useProfileDetail("conn-b", "doc"));
    renderHook(() => useProfileDetail("conn-c", "doc"));
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(4));
    expect(_profileDetailInflightSinceKeys().sort()).toEqual(["conn-b|doc", "conn-c|doc"]);
    invalidateProfileDetailCache("conn-c");
    expect(_profileDetailInflightSinceKeys()).toEqual(["conn-b|doc"]);
    await act(async () => { finishB({}); });
    expect(_profileDetailInflightSinceKeys()).toEqual([]);
    renderHook(() => useProfileDetail("conn-d", "doc"));
    expect(_profileDetailInflightSinceKeys()).toEqual(["conn-d|doc"]);
    _clearProfileDetailCache();
    expect(_profileDetailInflightSinceKeys()).toEqual([]);
  });

  it("a superseded fetch settling late never forgets the newer fetch for the same key", async () => {
    let finishOld;
    invoke
      .mockReturnValueOnce(new Promise((r) => { finishOld = r; }))
      .mockReturnValueOnce(new Promise(() => {}));
    renderHook(() => useProfileDetail("conn-e", "doc"));
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(1));
    invalidateProfileDetailCache("conn-e");
    renderHook(() => useProfileDetail("conn-e", "doc"));
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(2));
    await act(async () => { finishOld({}); });
    expect(_profileDetailInflightSinceKeys()).toEqual(["conn-e|doc"]);
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

  it("refresh() after a confirmed edit reads again instead of joining a read that started before it", async () => {
    const reads = [];
    invoke.mockImplementation(() => new Promise((resolve) => reads.push(resolve)));
    const { result } = renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => expect(reads).toHaveLength(1));
    confirmEdit(beginEdit("conn-a", "doc", { vision_model: "x/y" }));
    const vision = () => applyEdits({ name: "doc", vision_model: "old" }, "conn-a").vision_model;
    let refreshed;
    act(() => { refreshed = result.current.refresh(); });
    await act(async () => reads[0]({ vision_model: "old" }));
    expect(vision()).toBe("x/y");
    await waitFor(() => expect(reads).toHaveLength(2));
    await act(async () => { reads[1]({ vision_model: "x/y" }); await refreshed; });
    expect(vision()).toBe("old");
    expect(result.current.detail).toEqual({ vision_model: "x/y" });
  });

  it("falls back to {} (not null) when invoke rejects, so consumers stop spinning", async () => {
    invoke.mockRejectedValueOnce(new Error("daemon offline"));
    const { result } = renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => expect(result.current.detail).toEqual({}));
  });

  it("keeps cached detail when a forced background refresh fails", async () => {
    invoke
      .mockResolvedValueOnce({ models: ["a/b"] })
      .mockRejectedValueOnce(new Error("offline"));
    const first = renderHook(() => useProfileDetail("conn-a", "doc"));
    await waitFor(() => expect(first.result.current.detail).toEqual({ models: ["a/b"] }));
    first.unmount();

    const second = renderHook(() => useProfileDetail("conn-a", "doc", { refreshOnMount: true }));
    expect(second.result.current.detail).toEqual({ models: ["a/b"] });
    await waitFor(() => expect(second.result.current.loading).toBe(false));
    expect(second.result.current.detail).toEqual({ models: ["a/b"] });
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
