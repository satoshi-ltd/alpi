import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { useHostConnections } from "./useHostConnections.js";
import { pruneCachedMessages } from "../lib/workgroup-cache.js";
import { _resetDaemonBus } from "../lib/daemon-bus.js";

vi.mock("../lib/workgroup-cache.js", () => ({
  pruneCachedMessages: vi.fn(),
}));

let connectionStatusListener;

function makeConnections(active, statusByCid = {}) {
  return {
    active_id: active,
    connections: [
      { id: "local", status: statusByCid.local ?? "online", error: null, alpi_version: null },
      { id: "remote", status: statusByCid.remote ?? "online", error: null, alpi_version: null },
    ],
  };
}

function setProfileCache(connectionId, profiles, workgroups = []) {
  localStorage.setItem(`alf:profiles:v1:${connectionId}`, JSON.stringify(profiles));
  localStorage.setItem(`alf:workgroups:v1:${connectionId}`, JSON.stringify(workgroups));
}

function renderHostConnections() {
  const setSessionData = vi.fn();
  const clearAllTurns = vi.fn();
  const setRewriteDraft = vi.fn();
  const setActiveTask = vi.fn();
  const setView = vi.fn();
  const pendingTurnsRef = { current: {} };
  const r = renderHook(() =>
    useHostConnections({
      setSessionData,
      clearAllTurns,
      setRewriteDraft,
      setActiveTask,
      setView,
      pendingTurnsRef,
    }),
  );
  return { ...r, setView };
}

beforeEach(() => {
  vi.resetAllMocks();
  _resetDaemonBus();
  localStorage.clear();
  connectionStatusListener = null;
  listen.mockImplementation(async (eventName, cb) => {
    if (eventName === "connection-status") connectionStatusListener = cb;
    return () => {};
  });
});

describe("useHostConnections.onSetHostConnection", () => {
  it("flips active_id in the ref BEFORE pruning cache (otherwise the outgoing connection's cache gets pruned against the incoming workgroup list)", async () => {
    // initial: local active, both online, with profile_summaries + workgroups
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [{ name: "doc", model: "a/b" }];
      if (cmd === "workgroups") return [{ id: "wg-local" }];
      if (cmd === "host_connection_set_active") return null;
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() =>
      expect(result.current.profiles.map((p) => p.name)).toEqual(["doc"]),
    );

    // Seed remote cache that has DIFFERENT workgroup IDs.
    setProfileCache("remote", [{ name: "doc", model: "x/y" }], [{ id: "wg-remote" }]);
    pruneCachedMessages.mockClear();

    // Now switch.
    act(() => {
      result.current.onSetHostConnection("remote");
    });

    // First call from loadFromCache("remote") must receive the NEW active_id="remote", not the stale "local".
    expect(pruneCachedMessages).toHaveBeenCalled();
    const [activeIdArg, wgsArg] = pruneCachedMessages.mock.calls[0];
    expect(activeIdArg).toBe("remote");
    expect(wgsArg).toEqual([{ id: "wg-remote" }]);
  });

  it("resets pickerAlpi on switch so the new connection's default wins even when both share a profile name", async () => {
    // local default = doc; remote also has `doc` (NOT default) and `mirai` as its default. Without the reset, picker would stay on `doc` since both lists contain it; with the reset, it must re-derive to `mirai` (remote's default).
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [{ name: "doc", model: "a/b", is_default: true }];
      if (cmd === "workgroups") return [];
      if (cmd === "host_connection_set_active") return null;
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => expect(result.current.pickerAlpi).toBe("doc"));

    setProfileCache("remote", [
      { name: "doc", model: "x/y", is_default: false },
      { name: "mirai", model: "x/z", is_default: true },
    ]);

    act(() => {
      result.current.onSetHostConnection("remote");
    });

    expect(result.current.hostConnectionsRef.current.active_id).toBe("remote");
    expect(result.current.pickerAlpi).toBe("mirai");
  });

  it("rejects stale reload responses from a previous switch (A→B→A race)", async () => {
    let resolveFirstSummaries;
    let summariesCalls = 0;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") {
        summariesCalls++;
        if (summariesCalls === 1) {
          return new Promise((resolve) => {
            resolveFirstSummaries = resolve;
          });
        }
        return [{ name: "fresh-local-profile", model: "f/l" }];
      }
      if (cmd === "workgroups") return [];
      if (cmd === "host_connection_set_active") return null;
      return null;
    });

    const { result } = renderHostConnections();
    // Wait for mount-time reload to enter profile_summaries and hang.
    await waitFor(() => expect(summariesCalls).toBe(1));

    // First switch (local→remote) bumps connectionSwitchRef.
    act(() => {
      result.current.onSetHostConnection("remote");
    });
    await waitFor(() =>
      expect(result.current.hostConnectionsRef.current.active_id).toBe("remote"),
    );

    // Second switch (remote→local) bumps it again — and brings active_id back to "local", so the in-flight reload's `active_id === activeId` check would WRONGLY pass without the switchId guard.
    act(() => {
      result.current.onSetHostConnection("local");
    });
    await waitFor(() =>
      expect(result.current.hostConnectionsRef.current.active_id).toBe("local"),
    );

    // Now resolve the original (stale) reload kicked off at mount.
    await act(async () => {
      resolveFirstSummaries([{ name: "STALE-local-profile", model: "s/l" }]);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(
      result.current.profiles.some((p) => p.name === "STALE-local-profile"),
    ).toBe(false);
  });
});

describe("useHostConnections.touchWorkgroup", () => {
  it("patches only the matching workgroup's mtime locally, without any RPC", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [{ name: "doc", model: "a/b" }];
      if (cmd === "workgroups")
        return [
          { id: "wg-1", profile: "doc", mtime: 100 },
          { id: "wg-2", profile: "doc", mtime: 100 },
        ];
      return null;
    });
    const { result } = renderHostConnections();
    await waitFor(() => expect(result.current.workgroups.length).toBe(2));

    invoke.mockClear();
    act(() => result.current.touchWorkgroup("doc", "wg-1"));

    const w1 = result.current.workgroups.find((w) => w.id === "wg-1");
    const w2 = result.current.workgroups.find((w) => w.id === "wg-2");
    expect(w1.mtime).toBeGreaterThan(100);
    expect(w2.mtime).toBe(100);
    expect(invoke).not.toHaveBeenCalled();
  });

  it("is identity-stable when nothing matches (no spurious re-renders)", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [];
      if (cmd === "workgroups") return [{ id: "wg-1", profile: "doc", mtime: 100 }];
      return null;
    });
    const { result } = renderHostConnections();
    await waitFor(() => expect(result.current.workgroups.length).toBe(1));
    const before = result.current.workgroups;
    act(() => result.current.touchWorkgroup("other-profile", "wg-1"));
    expect(result.current.workgroups).toBe(before);
  });
});

describe("useHostConnections connection-status", () => {
  it("propagates update_available from a connection-status event without a full reload", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [{ name: "doc", model: "a/b" }];
      if (cmd === "workgroups") return [];
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() =>
      expect(result.current.hostConnections.connections.length).toBe(2),
    );

    await act(async () => {
      await connectionStatusListener({
        payload: { id: "remote", status: "online", update_available: "0.9.6" },
      });
    });

    const remote = result.current.hostConnections.connections.find((c) => c.id === "remote");
    expect(remote.update_available).toBe("0.9.6");
  });

  it("exposes syncing while the active connection profiles/workgroups refresh is in flight", async () => {
    let resolveProfiles;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") {
        return new Promise((resolve) => { resolveProfiles = resolve; });
      }
      if (cmd === "workgroups") return [];
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => expect(result.current.connectionSyncing).toBe(true));
    await act(async () => {
      resolveProfiles([{ name: "doc", model: "a/b" }]);
      await Promise.resolve();
    });
    await waitFor(() => expect(result.current.connectionSyncing).toBe(false));
  });

  it("keeps cached profiles visible while an active connection is temporarily offline", async () => {
    setProfileCache("local", [{ name: "cached-doc", model: "a/b" }], []);
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local", { local: "offline" });
      if (cmd === "profile_summaries") return [];
      if (cmd === "workgroups") return [];
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => {
      expect(result.current.profiles.map((p) => p.name)).toEqual(["cached-doc"]);
    });
  });

  it("clears syncing when a connection switch probe ends offline", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [{ name: "doc", model: "a/b" }];
      if (cmd === "workgroups") return [];
      if (cmd === "host_connection_set_active") return null;
      if (cmd === "host_connection_probe") return "offline";
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => expect(result.current.profiles.length).toBe(1));
    act(() => result.current.onSetHostConnection("remote"));
    expect(result.current.connectionSyncing).toBe(true);
    await waitFor(() => expect(result.current.connectionSyncing).toBe(false));
  });
});


describe("useHostConnections offline auto-reprobe", () => {
  it("re-probes the active connection while offline and stops once back online", async () => {
    let localStatus = "offline";
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local", { local: localStatus });
      if (cmd === "profile_summaries") return [];
      if (cmd === "workgroups") return [];
      return null;
    });
    vi.useFakeTimers();
    try {
      const { result } = renderHostConnections();
      // flush the initial async reload (microtasks) so state→offline and the effect installs a faked interval
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
        await Promise.resolve();
      });
      expect(
        result.current.hostConnections.connections.find((c) => c.id === "local")?.status,
      ).toBe("offline");
      invoke.mockClear();
      await act(async () => {
        vi.advanceTimersByTime(4000 * 3);
      });
      const offlineProbes = invoke.mock.calls.filter(
        ([c]) => c === "host_connections_probe_active",
      ).length;
      expect(offlineProbes).toBeGreaterThanOrEqual(2);

      localStatus = "online";
      await act(async () => {
        await connectionStatusListener({ payload: { id: "local", status: "online" } });
      });
      invoke.mockClear();
      await act(async () => {
        vi.advanceTimersByTime(4000 * 3);
      });
      const onlineProbes = invoke.mock.calls.filter(
        ([c]) => c === "host_connections_probe_active",
      ).length;
      expect(onlineProbes).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
});
