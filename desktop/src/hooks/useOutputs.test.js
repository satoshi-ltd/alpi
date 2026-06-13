import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import {
  fetchConnectionOutputs,
  pendingDeleteKeys,
  rowKey,
  useAllOutputs,
  useDeleteOutput,
  useMarkAllOutputsRead,
  useOutput,
} from "./useOutputs.js";


let daemonEventListener;
beforeEach(() => {
  vi.resetAllMocks();
  daemonEventListener = null;
  listen.mockImplementation(async (eventName, cb) => {
    if (eventName === "daemon-event") daemonEventListener = cb;
    return () => {};
  });
});


describe("useAllOutputs (cross-connection fan-out)", () => {
  it("fetchConnectionOutputs discovers profiles then lists outputs, tagging the connection", async () => {
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") {
        expect(params.connectionId).toBe("c1");
        return [{ name: "abby", accent: "#f00" }];
      }
      if (cmd === "outputs_list") {
        expect(params.connectionId).toBe("c1");
        return [{ id: "a1", created_at: 5, status: "unread" }];
      }
      return null;
    });
    const rows = await fetchConnectionOutputs({ id: "c1", name: "home" }, "unread");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      id: "a1", profile: "abby", accent: "#f00", connectionId: "c1", connectionName: "home",
    });
  });

  it("fetchConnectionOutputs falls back to the default profile when summaries is empty", async () => {
    invoke.mockImplementation(async (cmd) => (cmd === "profile_summaries" ? [] : [{ id: "d1", created_at: 1 }]));
    const rows = await fetchConnectionOutputs({ id: "c1", name: "home" });
    expect(rows[0].profile).toBe("default");
  });

  it("fetchConnectionOutputs returns [] when summaries throws (offline daemon)", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_summaries") throw new Error("offline");
      return [];
    });
    expect(await fetchConnectionOutputs({ id: "c1", name: "home" })).toEqual([]);
  });

  it("merges and sorts rows across all connections newest-first", async () => {
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") {
        return params.connectionId === "c1" ? [{ name: "abby" }] : [{ name: "vera" }];
      }
      if (cmd === "outputs_list") {
        return params.connectionId === "c1"
          ? [{ id: "a1", created_at: 100, status: "unread" }]
          : [{ id: "v1", created_at: 300, status: "unread" }];
      }
      return null;
    });
    const { result } = renderHook(() =>
      useAllOutputs({ connections: [{ id: "c1", name: "home" }, { id: "c2", name: "work" }] }),
    );
    await waitFor(() => expect(result.current.rows.length).toBe(2));
    expect(result.current.rows.map((r) => r.id)).toEqual(["v1", "a1"]);
    expect(result.current.rows.map((r) => r.connectionName)).toEqual(["work", "home"]);
  });

  it("clears rows when there are no connections", async () => {
    const { result } = renderHook(() => useAllOutputs({ connections: [] }));
    await waitFor(() => expect(result.current.rows).toEqual([]));
  });

  it("refreshes on a background-poll daemon-event (carries agent.message, not output.created)", async () => {
    let listCalls = 0;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_summaries") return [{ name: "abby" }];
      if (cmd === "outputs_list") { listCalls += 1; return []; }
      return null;
    });
    renderHook(() => useAllOutputs({ connections: [{ id: "c1", name: "home" }] }));
    await waitFor(() => expect(listCalls).toBe(1));
    await waitFor(() => expect(daemonEventListener).not.toBeNull());

    await act(async () => {
      daemonEventListener({
        payload: { connection_id: "c2", frame: { event: "agent.message", data: {} }, background: true },
      });
    });
    await waitFor(() => expect(listCalls).toBe(2));
  });

  it("does NOT refresh on a non-output active-stream event (no background flag) so chat churn doesn't refetch", async () => {
    let listCalls = 0;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_summaries") return [{ name: "abby" }];
      if (cmd === "outputs_list") { listCalls += 1; return []; }
      return null;
    });
    renderHook(() => useAllOutputs({ connections: [{ id: "c1", name: "home" }] }));
    await waitFor(() => expect(listCalls).toBe(1));
    await waitFor(() => expect(daemonEventListener).not.toBeNull());

    await act(async () => {
      daemonEventListener({
        payload: { connection_id: "c1", frame: { event: "session_changed", data: {} } },
      });
    });
    await new Promise((r) => setTimeout(r, 500));
    expect(listCalls).toBe(1);
  });
});


describe("local pub/sub after mutations", () => {
  it("markRead in one hook refreshes every mounted unified list — keeps modal rows + sidebar badge in sync", async () => {
    let listCalls = 0;
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") return [{ name: "abby" }];
      if (cmd === "outputs_list") {
        listCalls += 1;
        return [{ id: "abc123", profile: params.profile, created_at: 1, status: "unread", body: "x" }];
      }
      if (cmd === "outputs_read") {
        return { id: "abc123", profile: params.profile, created_at: 1, status: "unread", body: "x" };
      }
      if (cmd === "outputs_mark_read") {
        return { id: "abc123", profile: params.profile, created_at: 1, status: "read", body: "x" };
      }
      return null;
    });
    const list = renderHook(() => useAllOutputs({ connections: [{ id: "c1", name: "home" }] }));
    const detail = renderHook(() => useOutput("abby", "abc123"));
    await waitFor(() => expect(list.result.current.rows.length).toBe(1));
    await waitFor(() => expect(detail.result.current.row?.status).toBe("unread"));
    const before = listCalls;

    await act(async () => {
      await detail.result.current.markRead();
    });

    await waitFor(() => expect(listCalls).toBeGreaterThan(before));
  });

  it("mark_all_read with count > 0 refreshes all mounted unified lists; zero-count run does NOT", async () => {
    let listCalls = 0;
    let nextCount = 5;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_summaries") return [{ name: "abby" }];
      if (cmd === "outputs_list") {
        listCalls += 1;
        return [];
      }
      if (cmd === "outputs_mark_all_read") {
        return nextCount;
      }
      return null;
    });
    renderHook(() => useAllOutputs({ connections: [{ id: "c1", name: "home" }] }));
    const markAllHook = renderHook(() => useMarkAllOutputsRead());
    await waitFor(() => expect(listCalls).toBeGreaterThan(0));
    const before = listCalls;

    await act(async () => {
      const n = await markAllHook.result.current("abby");
      expect(n).toBe(5);
    });
    await waitFor(() => expect(listCalls).toBeGreaterThan(before));

    nextCount = 0;
    const before2 = listCalls;
    await act(async () => {
      const n = await markAllHook.result.current("abby");
      expect(n).toBe(0);
    });
    await new Promise((r) => setTimeout(r, 20));
    expect(listCalls).toBe(before2);
  });
});


describe("useDeleteOutput", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    for (const key of pendingDeleteKeys()) {
      const [connectionId, profile, id] = key.split(":");
      const { result } = renderHook(() => useDeleteOutput());
      result.current.cancel(profile, id, connectionId);
    }
    vi.useRealTimers();
  });

  it("schedule waits the delay then calls outputs_delete", async () => {
    invoke.mockResolvedValue(null);
    const { result } = renderHook(() => useDeleteOutput());

    act(() => {
      result.current.schedule("abby", "out-1", { connectionId: "c1" });
    });
    expect(invoke).not.toHaveBeenCalled();
    expect(pendingDeleteKeys()).toEqual(["c1:abby:out-1"]);

    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });
    expect(invoke).toHaveBeenCalledWith("outputs_delete", { profile: "abby", id: "out-1", connectionId: "c1" });
    expect(pendingDeleteKeys()).toEqual([]);
  });

  it("cancel before the timeout drops the timer without calling the RPC", async () => {
    invoke.mockResolvedValue(null);
    const { result } = renderHook(() => useDeleteOutput());

    act(() => {
      result.current.schedule("abby", "out-2", { connectionId: "c1" });
    });
    const cancelled = result.current.cancel("abby", "out-2", "c1");
    expect(cancelled).toBe(true);
    expect(pendingDeleteKeys()).toEqual([]);

    await act(async () => {
      vi.advanceTimersByTime(10000);
      await Promise.resolve();
    });
    expect(invoke).not.toHaveBeenCalled();
  });

  it("re-scheduling the same key cancels the previous timer", async () => {
    invoke.mockResolvedValue(null);
    const { result } = renderHook(() => useDeleteOutput());

    act(() => {
      result.current.schedule("abby", "out-3", { delayMs: 1000, connectionId: "c1" });
    });
    act(() => {
      vi.advanceTimersByTime(500);
    });
    act(() => {
      result.current.schedule("abby", "out-3", { delayMs: 1000, connectionId: "c1" });
    });
    act(() => {
      vi.advanceTimersByTime(600);
    });
    expect(invoke).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(500);
      await Promise.resolve();
    });
    expect(invoke).toHaveBeenCalledTimes(1);
  });

  it("namespaces by connectionId so the same profile:id on two daemons is independent", async () => {
    invoke.mockResolvedValue(null);
    const { result } = renderHook(() => useDeleteOutput());

    act(() => {
      result.current.schedule("default", "shared", { connectionId: "c1" });
      result.current.schedule("default", "shared", { connectionId: "c2" });
    });
    expect(pendingDeleteKeys().sort()).toEqual(["c1:default:shared", "c2:default:shared"]);

    result.current.cancel("default", "shared", "c1");
    expect(pendingDeleteKeys()).toEqual(["c2:default:shared"]);
  });
});


describe("rowKey (modal hide/delete namespacing)", () => {
  it("namespaces by connectionId so the same profile:id on two daemons is distinct", () => {
    const a = { connectionId: "c1", profile: "default", id: "o1" };
    const b = { connectionId: "c2", profile: "default", id: "o1" };
    expect(rowKey(a)).toBe("c1:default:o1");
    expect(rowKey(a)).not.toBe(rowKey(b));
  });

  it("hiding one connection's row leaves the other daemon's identical id visible", () => {
    const rows = [
      { connectionId: "c1", profile: "default", id: "o1" },
      { connectionId: "c2", profile: "default", id: "o1" },
    ];
    const hidden = new Set([rowKey(rows[0])]);
    const visible = rows.filter((r) => !hidden.has(rowKey(r)));
    expect(visible).toEqual([{ connectionId: "c2", profile: "default", id: "o1" }]);
  });
});
