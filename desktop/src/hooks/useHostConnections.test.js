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
  const clearTurnsForConnection = vi.fn();
  const setRewriteDraft = vi.fn();
  const setActiveTask = vi.fn();
  const setView = vi.fn();
  const notify = vi.fn();
  const r = renderHook(() =>
    useHostConnections({
      setSessionData,
      clearTurnsForConnection,
      setRewriteDraft,
      setActiveTask,
      setView,
      notify,
    }),
  );
  return { ...r, setView, clearTurnsForConnection, notify };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.restoreAllMocks();
  _resetDaemonBus();
  localStorage.clear();
  connectionStatusListener = null;
  listen.mockImplementation(async (eventName, cb) => {
    if (eventName === "connection-status") connectionStatusListener = cb;
    return () => {};
  });
});

describe("useHostConnections cache persistence", () => {
  it("evicts only regenerable caches and retries a full workgroup snapshot", async () => {
    localStorage.setItem("alpi.session.cache.v1.local.mira.s-1", "cached session");
    localStorage.setItem("alpi.workgroup.cache.local.mira.wg-live", "cached posts");
    localStorage.setItem("alpi.drafts.v1", "important draft");
    const nativeSetItem = Storage.prototype.setItem;
    let workgroupWrites = 0;
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(function setItem(key, value) {
      if (key === "alf:workgroups:v1:local" && workgroupWrites++ === 0) {
        throw new DOMException("The quota has been exceeded.", "QuotaExceededError");
      }
      return nativeSetItem.call(this, key, value);
    });
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [{ name: "mira", model: "a/b" }];
      if (cmd === "workgroups") {
        return [{ id: "wg-live", profile: "mira", name: "Live workgroup" }];
      }
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => expect(result.current.workgroups).toHaveLength(1));

    expect(localStorage.getItem("alpi.session.cache.v1.local.mira.s-1")).toBeNull();
    expect(localStorage.getItem("alpi.workgroup.cache.local.mira.wg-live")).toBeNull();
    expect(localStorage.getItem("alpi.drafts.v1")).toBe("important draft");
    expect(JSON.parse(localStorage.getItem("alf:workgroups:v1:local"))).toEqual([
      { id: "wg-live", profile: "mira", name: "Live workgroup" },
    ]);
  });
});

describe("useHostConnections.onSetHostConnection", () => {
  it("flips active_id in the ref BEFORE pruning cache (otherwise the outgoing connection's cache gets pruned against the incoming workgroup list)", async () => {
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

    setProfileCache("remote", [{ name: "doc", model: "x/y" }], [{ id: "wg-remote" }]);
    pruneCachedMessages.mockClear();

    act(() => {
      result.current.onSetHostConnection("remote");
    });

    expect(pruneCachedMessages).toHaveBeenCalled();
    const [activeIdArg, wgsArg] = pruneCachedMessages.mock.calls[0];
    expect(activeIdArg).toBe("remote");
    expect(wgsArg).toEqual([{ id: "wg-remote" }]);
  });

  it("keeps in-flight turns alive when switching the active connection (no cancel, no clear)", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [{ name: "doc", model: "a/b" }];
      if (cmd === "workgroups") return [];
      if (cmd === "host_connection_set_active") return null;
      return null;
    });

    const { result, clearTurnsForConnection } = renderHostConnections();
    await waitFor(() =>
      expect(result.current.profiles.map((p) => p.name)).toEqual(["doc"]),
    );

    invoke.mockClear();
    clearTurnsForConnection.mockClear();
    await act(async () => {
      result.current.onSetHostConnection("remote");
    });
    await waitFor(() =>
      expect(
        invoke.mock.calls.some(([cmd]) => cmd === "host_connection_set_active"),
      ).toBe(true),
    );

    expect(invoke.mock.calls.some(([cmd]) => cmd === "chat_cancel")).toBe(false);
    expect(clearTurnsForConnection).not.toHaveBeenCalled();
  });

  it("resets pickerAlpi on switch so the new connection's default wins even when both share a profile name", async () => {
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

  it("notifies and falls back to the previous connection when activating a revoked one fails", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [{ name: "doc", model: "a/b" }];
      if (cmd === "workgroups") return [];
      if (cmd === "host_connection_set_active") {
        throw new Error("connection is revoked: remote");
      }
      return null;
    });

    const { result, notify } = renderHostConnections();
    await waitFor(() => expect(result.current.profiles.length).toBe(1));

    await act(async () => {
      result.current.onSetHostConnection("remote");
    });

    await waitFor(() =>
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: "error",
          message: expect.stringContaining("revoked"),
        }),
      ),
    );
    expect(result.current.hostConnectionsRef.current.active_id).toBe("local");
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
    await waitFor(() => expect(summariesCalls).toBe(1));

    act(() => {
      result.current.onSetHostConnection("remote");
    });
    await waitFor(() =>
      expect(result.current.hostConnectionsRef.current.active_id).toBe("remote"),
    );

    act(() => {
      result.current.onSetHostConnection("local");
    });
    await waitFor(() =>
      expect(result.current.hostConnectionsRef.current.active_id).toBe("local"),
    );

    await act(async () => {
      resolveFirstSummaries([{ name: "STALE-local-profile", model: "s/l" }]);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(
      result.current.profiles.some((p) => p.name === "STALE-local-profile"),
    ).toBe(false);
  });

  it("does not let a lagging host_connections snapshot undo an optimistic switch", async () => {
    let releaseSetActive;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [{ name: "doc", model: "a/b" }];
      if (cmd === "workgroups") return [];
      if (cmd === "host_connection_set_active") {
        return new Promise((resolve) => { releaseSetActive = resolve; });
      }
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => expect(result.current.hostConnections.connections.length).toBe(2));

    act(() => result.current.onSetHostConnection("remote"));
    await waitFor(() => expect(result.current.hostConnections.active_id).toBe("remote"));

    await act(async () => {
      await result.current.reload();
    });
    expect(result.current.hostConnections.active_id).toBe("remote");

    await act(async () => {
      releaseSetActive();
      await Promise.resolve();
    });
  });
});

describe("useHostConnections.onAddHostConnection", () => {
  it.each([
    [
      JSON.stringify({ u: "wss://client.example.com", n: "Client", t: "secret" }),
      "wss://client.example.com",
    ],
    [
      "alpi://device?host=100.64.0.1&port=49200&name=Legacy&token=secret",
      "ws://100.64.0.1:49200",
      { token: "secret" },
    ],
    [
      "alpi://device?url=wss%3A%2F%2Fclient.example.com&name=Client&pairing_token=grant",
      "wss://client.example.com",
      { pairingToken: "grant" },
    ],
  ].map((row) => row.length === 2 ? [...row, { token: "secret" }] : row))(
    "stores a complete endpoint URL from new and legacy pairings",
    async (payload, url, credential) => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries" || cmd === "workgroups") return [];
      return null;
    });
    const { result } = renderHostConnections();
    await waitFor(() => expect(result.current.hostConnections.connections.length).toBe(2));
    invoke.mockClear();

    await act(async () => { await result.current.onAddHostConnection(payload); });

    expect(invoke).toHaveBeenCalledWith("host_connection_add_remote", {
      name: expect.any(String),
      url,
      ...credential,
    });
    },
  );
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

  it("applies a role change (admin→member) from a connection-status event, and a null role never clears it", async () => {
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
    const roleOf = () =>
      result.current.hostConnections.connections.find((c) => c.id === "remote").role;

    await act(async () => {
      await connectionStatusListener({ payload: { id: "remote", status: "online", role: "member" } });
    });
    expect(roleOf()).toBe("member");

    await act(async () => {
      await connectionStatusListener({ payload: { id: "remote", status: "offline" } });
    });
    expect(roleOf()).toBe("member");
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

  it("keeps cached profiles visible while an active connection is disabled", async () => {
    setProfileCache("remote", [{ name: "cached-doc", model: "a/b" }], []);
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") {
        return makeConnections("remote", { remote: "disabled" });
      }
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => {
      expect(result.current.connectionSyncing).toBe(false);
      expect(result.current.profiles.map((profile) => profile.name)).toEqual([
        "cached-doc",
      ]);
    });
  });

  it("keeps cached remote profiles when profile_summaries rejects", async () => {
    setProfileCache("remote", [{ name: "cached-remote", model: "a/b" }], []);
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("remote");
      if (cmd === "profile_summaries") throw new Error("read timeout");
      if (cmd === "workgroups") return [];
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => {
      expect(result.current.profiles.map((p) => p.name)).toEqual(["cached-remote"]);
    });
    expect(invoke.mock.calls.some(([cmd]) => cmd === "profiles")).toBe(false);
  });

  it("keeps cached profiles and workgroups when workgroups rejects", async () => {
    setProfileCache(
      "local",
      [{ name: "cached-doc", model: "a/b" }],
      [{ id: "wg-cached", profile: "cached-doc" }],
    );
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [{ name: "fresh-doc", model: "a/b" }];
      if (cmd === "workgroups") throw new Error("read timeout");
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => {
      expect(result.current.profiles.map((p) => p.name)).toEqual(["cached-doc"]);
      expect(result.current.workgroups.map((w) => w.id)).toEqual(["wg-cached"]);
    });
  });

  it("does not fall back to local profiles when an online remote returns no summaries", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("remote");
      if (cmd === "profile_summaries") return [];
      if (cmd === "workgroups") return [];
      if (cmd === "profiles") return [{ name: "local-only" }];
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => expect(result.current.connectionSyncing).toBe(false));
    expect(result.current.profiles.map((p) => p.name)).toEqual([]);
    expect(invoke.mock.calls.some(([cmd]) => cmd === "profiles")).toBe(false);
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

  it("clears syncing when a connection switch probe ends disabled", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [{ name: "doc", model: "a/b" }];
      if (cmd === "workgroups") return [];
      if (cmd === "host_connection_set_active") return null;
      if (cmd === "host_connection_probe") return "disabled";
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => expect(result.current.profiles.length).toBe(1));
    act(() => result.current.onSetHostConnection("remote"));
    await waitFor(() => expect(result.current.connectionSyncing).toBe(false));
  });
});


describe("useHostConnections.connectionSwitching", () => {
  it("stays false during background reloads even while syncing", async () => {
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
    expect(result.current.connectionSwitching).toBe(false);
    await act(async () => { resolveProfiles([]); });
  });

  it("turns on at switch start and off when the probe ends offline", async () => {
    let resolveProbe;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local");
      if (cmd === "profile_summaries") return [{ name: "doc", model: "a/b" }];
      if (cmd === "workgroups") return [];
      if (cmd === "host_connection_set_active") return null;
      if (cmd === "host_connection_probe") {
        return new Promise((resolve) => { resolveProbe = resolve; });
      }
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => expect(result.current.connectionSyncing).toBe(false));

    act(() => result.current.onSetHostConnection("remote"));
    expect(result.current.connectionSwitching).toBe(true);

    await waitFor(() => expect(typeof resolveProbe).toBe("function"));
    await act(async () => { resolveProbe("offline"); });
    await waitFor(() => expect(result.current.connectionSwitching).toBe(false));
  });

  it("holds through probe→online→reload and clears once the new profiles land", async () => {
    let active = "local";
    let resolveRemoteSummaries;
    invoke.mockImplementation(async (cmd, args) => {
      if (cmd === "host_connections") return makeConnections(active);
      if (cmd === "host_connection_set_active") {
        active = args.id;
        return null;
      }
      if (cmd === "host_connection_probe") return "online";
      if (cmd === "profile_summaries") {
        if (active === "remote") {
          return new Promise((resolve) => { resolveRemoteSummaries = resolve; });
        }
        return [{ name: "doc", model: "a/b" }];
      }
      if (cmd === "workgroups") return [];
      return null;
    });

    const { result } = renderHostConnections();
    await waitFor(() => expect(result.current.connectionSyncing).toBe(false));

    act(() => result.current.onSetHostConnection("remote"));
    expect(result.current.connectionSwitching).toBe(true);

    await waitFor(() => expect(typeof resolveRemoteSummaries).toBe("function"));
    expect(result.current.connectionSwitching).toBe(true);

    await act(async () => { resolveRemoteSummaries([{ name: "mirai", model: "x/y" }]); });
    await waitFor(() => expect(result.current.connectionSwitching).toBe(false));
    expect(result.current.profiles.map((p) => p.name)).toEqual(["mirai"]);
  });
});

describe("useHostConnections offline auto-reprobe", () => {
  function mockOfflineLocal(getStatus) {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") return makeConnections("local", { local: getStatus() });
      if (cmd === "profile_summaries") return [];
      if (cmd === "workgroups") return [];
      return null;
    });
  }

  const probeActiveCount = () =>
    invoke.mock.calls.filter(([c]) => c === "host_connections_probe_active").length;

  it("re-probes offline with exponential backoff and stops once back online", async () => {
    const rnd = vi.spyOn(Math, "random").mockReturnValue(0.5);
    let localStatus = "offline";
    mockOfflineLocal(() => localStatus);
    vi.useFakeTimers();
    try {
      const { result } = renderHostConnections();
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
        await Promise.resolve();
      });
      expect(
        result.current.hostConnections.connections.find((c) => c.id === "local")?.status,
      ).toBe("offline");

      invoke.mockClear();
      await act(async () => { vi.advanceTimersByTime(5000); });
      expect(probeActiveCount()).toBeGreaterThanOrEqual(1);

      invoke.mockClear();
      await act(async () => { vi.advanceTimersByTime(200000); });
      expect(probeActiveCount()).toBeLessThan(12);

      localStatus = "online";
      await act(async () => {
        await connectionStatusListener({ payload: { id: "local", status: "online" } });
      });
      invoke.mockClear();
      await act(async () => { vi.advanceTimersByTime(200000); });
      expect(probeActiveCount()).toBe(0);
    } finally {
      vi.useRealTimers();
      rnd.mockRestore();
    }
  });

  it("jitters the reprobe delay below the base interval", async () => {
    const rnd = vi.spyOn(Math, "random").mockReturnValue(0);
    mockOfflineLocal(() => "offline");
    vi.useFakeTimers();
    try {
      renderHostConnections();
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
        await Promise.resolve();
      });
      invoke.mockClear();
      await act(async () => { vi.advanceTimersByTime(3300); });
      expect(probeActiveCount()).toBeGreaterThanOrEqual(1);
    } finally {
      vi.useRealTimers();
      rnd.mockRestore();
    }
  });
});
