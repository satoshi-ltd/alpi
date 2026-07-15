import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import {
  _resetOutputsMemory,
  fetchConnectionOutputs,
  pendingDeleteKeys,
  rowKey,
  useAllOutputs,
  useDeleteOutput,
  useMarkAllOutputsRead,
  useOutput,
} from "./useOutputs.js";
import { _resetDaemonBus } from "../lib/daemon-bus.js";


let daemonEventListener;
beforeEach(() => {
  vi.resetAllMocks();
  _resetOutputsMemory();
  _resetDaemonBus();
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
        return [{ name: "abby", accent: "#f00", voice_id: "en-GB-SoniaNeural" }];
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
      id: "a1", profile: "abby", accent: "#f00", voice_id: "en-GB-SoniaNeural", connectionId: "c1", connectionName: "home",
    });
  });

  it("fetchConnectionOutputs falls back to the default profile when summaries is empty", async () => {
    invoke.mockImplementation(async (cmd) => (cmd === "profile_summaries" ? [] : [{ id: "d1", created_at: 1 }]));
    const rows = await fetchConnectionOutputs({ id: "c1", name: "home" });
    expect(rows[0].profile).toBe("default");
  });

  it("fetchConnectionOutputs returns null when summaries throws — failure must never read as an empty inbox", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_summaries") throw new Error("offline");
      return null;
    });
    expect(await fetchConnectionOutputs({ id: "c1", name: "home" })).toBeNull();
  });

  it("a partially failing daemon keeps the failed profile's previous rows and updates the rest", async () => {
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") return [{ name: "ok" }, { name: "broken" }];
      if (cmd === "outputs_list") {
        if (params.profile === "broken") throw new Error("timeout");
        return [{ id: "fresh", created_at: 9, profile: "ok" }];
      }
      return null;
    });
    const previous = [
      { id: "old-ok", created_at: 1, profile: "ok" },
      { id: "old-broken", created_at: 2, profile: "broken" },
    ];
    const rows = await fetchConnectionOutputs({ id: "c1", name: "home" }, null, previous);
    expect(rows.map((r) => r.id).sort()).toEqual(["fresh", "old-broken"]);
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


describe("useAllOutputs cold-start discipline (per-connection)", () => {
  it("fetches the active connection immediately and defers the rest", async () => {
    const calls = [];
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") { calls.push(params.connectionId); return [{ name: "p" }]; }
      if (cmd === "outputs_list") return [];
      return null;
    });
    renderHook(() =>
      useAllOutputs({
        connections: [{ id: "c1", name: "home" }, { id: "c2", name: "work" }],
        activeId: "c1",
        deferMs: 80,
      }),
    );
    await waitFor(() => expect(calls).toContain("c1"));
    expect(calls).not.toContain("c2");
    await waitFor(() => expect(calls).toContain("c2"), { timeout: 2000 });
  });

  it("unknown→probing→online fetches exactly once, on the online transition", async () => {
    const calls = [];
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") { calls.push(params.connectionId); return [{ name: "p" }]; }
      if (cmd === "outputs_list") return [];
      return null;
    });
    const conn = (status) => [{ id: "c1", name: "home", status }];
    const { rerender } = renderHook(({ connections }) => useAllOutputs({ connections }), {
      initialProps: { connections: conn("unknown") },
    });
    await new Promise((r) => setTimeout(r, 50));
    expect(calls).toEqual([]);
    rerender({ connections: conn("probing") });
    await new Promise((r) => setTimeout(r, 50));
    expect(calls).toEqual([]);
    rerender({ connections: conn("online") });
    await waitFor(() => expect(calls).toEqual(["c1"]));
    rerender({ connections: conn("online") });
    await new Promise((r) => setTimeout(r, 50));
    expect(calls).toEqual(["c1"]);
  });

  it.each(["offline", "disabled"])(
    "a connection going %s drops its rows without any refetch",
    async (status) => {
    let listCalls = 0;
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") return [{ name: "p" }];
      if (cmd === "outputs_list") { listCalls += 1; return [{ id: "o1", created_at: 1, profile: "p" }]; }
      return null;
    });
    const conn = (status) => [{ id: "c1", name: "home", status }];
    const { result, rerender } = renderHook(({ connections }) => useAllOutputs({ connections }), {
      initialProps: { connections: conn("online") },
    });
    await waitFor(() => expect(result.current.rows.length).toBe(1));
    const before = listCalls;
    rerender({ connections: conn(status) });
    await waitFor(() => expect(result.current.rows).toEqual([]));
    expect(listCalls).toBe(before);
    },
  );

  it("an output event refreshes only its own connection", async () => {
    const calls = [];
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") { calls.push(params.connectionId); return [{ name: "p" }]; }
      if (cmd === "outputs_list") return [];
      return null;
    });
    renderHook(() =>
      useAllOutputs({ connections: [{ id: "c1", name: "home" }, { id: "c2", name: "work" }] }),
    );
    await waitFor(() => expect(calls).toContain("c1"));
    await waitFor(() => expect(calls).toContain("c2"));
    await waitFor(() => expect(daemonEventListener).not.toBeNull());
    calls.length = 0;
    await act(async () => {
      daemonEventListener({
        payload: { connection_id: "c2", frame: { event: "output.created", data: {} } },
      });
    });
    await waitFor(() => expect(calls).toEqual(["c2"]));
  });
});


describe("useAllOutputs review hardening", () => {
  it("enabled:false runs no fan-out; enabling fetches active first, secondary after the defer", async () => {
    const calls = [];
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") { calls.push(params.connectionId); return [{ name: "p" }]; }
      if (cmd === "outputs_list") return [];
      return null;
    });
    const conns = [{ id: "c1", name: "home" }, { id: "c2", name: "work" }];
    const { rerender } = renderHook(
      ({ enabled }) => useAllOutputs({ connections: conns, activeId: "c1", deferMs: 80, enabled }),
      { initialProps: { enabled: false } },
    );
    await new Promise((r) => setTimeout(r, 60));
    expect(calls).toEqual([]);
    rerender({ enabled: true });
    await waitFor(() => expect(calls).toContain("c1"));
    expect(calls).not.toContain("c2");
    await waitFor(() => expect(calls).toContain("c2"), { timeout: 2000 });
  });

  it("disabling before the defer cancels the secondary connection's fetch", async () => {
    const calls = [];
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") { calls.push(params.connectionId); return [{ name: "p" }]; }
      if (cmd === "outputs_list") return [];
      return null;
    });
    const conns = [{ id: "c1", name: "home" }, { id: "c2", name: "work" }];
    const { rerender } = renderHook(
      ({ enabled }) => useAllOutputs({ connections: conns, activeId: "c1", deferMs: 80, enabled }),
      { initialProps: { enabled: true } },
    );
    await waitFor(() => expect(calls).toContain("c1"));
    rerender({ enabled: false });
    await new Promise((r) => setTimeout(r, 200));
    expect(calls).not.toContain("c2");
  });

  it("a response resolving after disable does not update rows", async () => {
    let resolveList;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_summaries") return [{ name: "p" }];
      if (cmd === "outputs_list") return new Promise((res) => { resolveList = res; });
      return null;
    });
    const conns = [{ id: "c1", name: "home" }];
    const { result, rerender } = renderHook(
      ({ enabled }) => useAllOutputs({ connections: conns, enabled }),
      { initialProps: { enabled: true } },
    );
    await waitFor(() => expect(typeof resolveList).toBe("function"));
    rerender({ enabled: false });
    await act(async () => {
      resolveList([{ id: "late", created_at: 5, profile: "p" }]);
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(result.current.rows).toEqual([]);
  });

  it("re-enabling after a close refetches the active connection from scratch", async () => {
    const calls = [];
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") { calls.push(params.connectionId); return [{ name: "p" }]; }
      if (cmd === "outputs_list") return [];
      return null;
    });
    const conns = [{ id: "c1", name: "home" }];
    const { rerender } = renderHook(
      ({ enabled }) => useAllOutputs({ connections: conns, activeId: "c1", enabled }),
      { initialProps: { enabled: true } },
    );
    await waitFor(() => expect(calls).toEqual(["c1"]));
    rerender({ enabled: false });
    rerender({ enabled: true });
    await waitFor(() => expect(calls).toEqual(["c1", "c1"]));
  });

  it("enabled:false never registers a daemon-bus listener", async () => {
    invoke.mockImplementation(async () => []);
    renderHook(() => useAllOutputs({ connections: [{ id: "c1", name: "home" }], enabled: false }));
    await new Promise((r) => setTimeout(r, 30));
    expect(daemonEventListener).toBeNull();
  });

  it("an in-flight response cannot resurrect rows after the connection went offline", async () => {
    let resolveList;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_summaries") return [{ name: "p" }];
      if (cmd === "outputs_list") {
        return new Promise((res) => { resolveList = res; });
      }
      return null;
    });
    const conn = (status) => [{ id: "c1", name: "home", status }];
    const { result, rerender } = renderHook(({ connections }) => useAllOutputs({ connections }), {
      initialProps: { connections: conn("online") },
    });
    await waitFor(() => expect(typeof resolveList).toBe("function"));
    rerender({ connections: conn("offline") });
    await act(async () => {
      resolveList([{ id: "zombie", created_at: 9, profile: "p" }]);
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(result.current.rows).toEqual([]);
  });

  it("changing the status filter drops the old query's rows and refetches", async () => {
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") return [{ name: "p" }];
      if (cmd === "outputs_list") {
        return params.status === "unread"
          ? [{ id: "u1", created_at: 1, profile: "p", status: "unread" }]
          : [
            { id: "u1", created_at: 1, profile: "p", status: "unread" },
            { id: "r1", created_at: 2, profile: "p", status: "read" },
          ];
      }
      return null;
    });
    const { result, rerender } = renderHook(
      ({ status }) => useAllOutputs({ connections: [{ id: "c1", name: "home" }], status }),
      { initialProps: { status: "unread" } },
    );
    await waitFor(() => expect(result.current.rows.map((r) => r.id)).toEqual(["u1"]));
    rerender({ status: undefined });
    await waitFor(() => expect(result.current.rows.map((r) => r.id)).toEqual(["r1", "u1"]));
  });
});


describe("useAllOutputs warm start (rows memory)", () => {
  it("a remount paints remembered rows instantly while the refetch is still pending", async () => {
    let resolveList = null;
    let firstCall = true;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_summaries") return [{ name: "p" }];
      if (cmd === "outputs_list") {
        if (firstCall) {
          firstCall = false;
          return [{ id: "o1", created_at: 7, profile: "p" }];
        }
        return new Promise((res) => { resolveList = res; });
      }
      return null;
    });
    const conns = [{ id: "c1", name: "home" }];
    const first = renderHook(() => useAllOutputs({ connections: conns }));
    await waitFor(() => expect(first.result.current.rows.length).toBe(1));
    first.unmount();

    const second = renderHook(() => useAllOutputs({ connections: conns }));
    await waitFor(() => expect(second.result.current.rows.map((r) => r.id)).toEqual(["o1"]));
    expect(second.result.current.loading).toBe(true);
    await act(async () => {
      resolveList([{ id: "o2", created_at: 9, profile: "p" }]);
      await new Promise((r) => setTimeout(r, 10));
    });
    expect(second.result.current.rows.map((r) => r.id)).toEqual(["o2"]);
  });

  it("deferMs 0 fetches every connection immediately (inbox-open semantics)", async () => {
    const calls = [];
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") { calls.push(params.connectionId); return [{ name: "p" }]; }
      if (cmd === "outputs_list") return [];
      return null;
    });
    renderHook(() =>
      useAllOutputs({
        connections: [{ id: "c1", name: "home" }, { id: "c2", name: "work" }],
        activeId: "c1",
        deferMs: 0,
      }),
    );
    await waitFor(() => expect(calls).toContain("c1"));
    await waitFor(() => expect(calls).toContain("c2"), { timeout: 1500 });
  });

  it("an offline flip also forgets the remembered rows", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_summaries") return [{ name: "p" }];
      if (cmd === "outputs_list") return [{ id: "o1", created_at: 1, profile: "p" }];
      return null;
    });
    const conn = (status) => [{ id: "c1", name: "home", status }];
    const { result, rerender, unmount } = renderHook(
      ({ connections }) => useAllOutputs({ connections }),
      { initialProps: { connections: conn("online") } },
    );
    await waitFor(() => expect(result.current.rows.length).toBe(1));
    rerender({ connections: conn("offline") });
    await waitFor(() => expect(result.current.rows).toEqual([]));
    unmount();
    invoke.mockImplementation(async () => new Promise(() => {}));
    const second = renderHook(() => useAllOutputs({ connections: conn("online") }));
    await new Promise((r) => setTimeout(r, 30));
    expect(second.result.current.rows).toEqual([]);
  });
});


describe("useAllOutputs member connections", () => {
  it("never fetches outputs from a member-role connection and drops its stale rows", async () => {
    const calls = [];
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") { calls.push(params.connectionId); return [{ name: "p" }]; }
      if (cmd === "outputs_list") return [{ id: "o", created_at: 1, profile: "p" }];
      return null;
    });
    const conns = (role) => [
      { id: "c1", name: "home", role: "admin" },
      { id: "c2", name: "work", role },
    ];
    const { result, rerender } = renderHook(
      ({ connections }) => useAllOutputs({ connections }),
      { initialProps: { connections: conns("admin") } },
    );
    await waitFor(() => expect(calls.sort()).toEqual(["c1", "c2"]));
    await waitFor(() => expect(result.current.rows.length).toBe(2));
    calls.length = 0;
    rerender({ connections: conns("member") });
    await waitFor(() => expect(result.current.rows.length).toBe(1));
    await new Promise((r) => setTimeout(r, 50));
    expect(calls).toEqual([]);
  });

  it("refresh(memberId) makes no RPC — the guard is before the fetch, not after", async () => {
    const calls = [];
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") { calls.push(params.connectionId); return [{ name: "p" }]; }
      if (cmd === "outputs_list") return [{ id: "o", created_at: 1, profile: "p" }];
      return null;
    });
    const connections = [
      { id: "c1", name: "home", role: "admin" },
      { id: "c2", name: "work", role: "member" },
    ];
    const { result } = renderHook(() => useAllOutputs({ connections }));
    await waitFor(() => expect(calls).toEqual(["c1"]));
    calls.length = 0;
    await act(async () => { await result.current.refresh("c2"); });
    expect(calls).toEqual([]);
  });

  it("an event-driven refresh scoped to a member connection makes no RPC", async () => {
    const calls = [];
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") { calls.push(params.connectionId); return [{ name: "p" }]; }
      if (cmd === "outputs_list") return [{ id: "o", created_at: 1, profile: "p" }];
      return null;
    });
    const connections = [
      { id: "c1", name: "home", role: "admin" },
      { id: "c2", name: "work", role: "member" },
    ];
    renderHook(() => useAllOutputs({ connections }));
    await waitFor(() => expect(calls).toEqual(["c1"]));
    await waitFor(() => expect(daemonEventListener).not.toBeNull());
    calls.length = 0;
    await act(async () => {
      daemonEventListener({
        payload: { connection_id: "c2", frame: { event: "agent.message", data: {} }, background: true },
      });
      await new Promise((r) => setTimeout(r, 500));
    });
    expect(calls).toEqual([]);
  });
});


describe("useAllOutputs credential and failure hardening", () => {
  it("re-pairing the same connection id with a new token never shows the old credential's rows", async () => {
    let resolveList = null;
    let call = 0;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_summaries") return [{ name: "p" }];
      if (cmd === "outputs_list") {
        call += 1;
        if (call === 1) return [{ id: "secret-A", created_at: 5, profile: "p" }];
        return new Promise((res) => { resolveList = res; });
      }
      return null;
    });
    const conn = (tokenId) => [{ id: "c1", name: "home", token_id: tokenId }];
    const { result, rerender } = renderHook(
      ({ connections }) => useAllOutputs({ connections }),
      { initialProps: { connections: conn("AAAAAAAA") } },
    );
    await waitFor(() => expect(result.current.rows.map((r) => r.id)).toEqual(["secret-A"]));
    rerender({ connections: conn("BBBBBBBB") });
    await waitFor(() => expect(result.current.rows).toEqual([]));
    expect(typeof resolveList).toBe("function");
    await act(async () => {
      resolveList([{ id: "b-row", created_at: 7, profile: "p" }]);
      await new Promise((r) => setTimeout(r, 10));
    });
    expect(result.current.rows.map((r) => r.id)).toEqual(["b-row"]);
  });

  it("a total revalidation failure keeps the remembered rows on screen", async () => {
    let failing = false;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_summaries") {
        if (failing) throw new Error("net down");
        return [{ name: "p" }];
      }
      if (cmd === "outputs_list") return [{ id: "kept", created_at: 3, profile: "p" }];
      return null;
    });
    const conns = [{ id: "c1", name: "home" }];
    const first = renderHook(() => useAllOutputs({ connections: conns }));
    await waitFor(() => expect(first.result.current.rows.length).toBe(1));
    first.unmount();
    failing = true;
    const second = renderHook(() => useAllOutputs({ connections: conns }));
    await waitFor(() => expect(second.result.current.rows.map((r) => r.id)).toEqual(["kept"]));
    await waitFor(() => expect(second.result.current.loading).toBe(false));
    expect(second.result.current.rows.map((r) => r.id)).toEqual(["kept"]);
  });

  it("explicit open drains connections with bounded concurrency, not a time stagger", async () => {
    const resolvers = new Map();
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") {
        return new Promise((res) => { resolvers.set(params.connectionId, res); });
      }
      if (cmd === "outputs_list") return [];
      return null;
    });
    const conns = Array.from({ length: 9 }, (_, i) => ({ id: `c${i}`, name: `n${i}` }));
    renderHook(() => useAllOutputs({ connections: conns, activeId: "c0", deferMs: 0 }));
    await waitFor(() => expect(resolvers.size).toBe(6));
    await new Promise((r) => setTimeout(r, 50));
    expect(resolvers.size).toBe(6);
    await act(async () => {
      resolvers.get("c0")([{ name: "p" }]);
      await new Promise((r) => setTimeout(r, 20));
    });
    await waitFor(() => expect(resolvers.size).toBeGreaterThanOrEqual(7));
  });

  it("loading stays true while queued connections remain, and drops only when the last one lands", async () => {
    const resolvers = new Map();
    invoke.mockImplementation(async (cmd, params) => {
      if (cmd === "profile_summaries") {
        return new Promise((res) => { resolvers.set(params.connectionId, res); });
      }
      if (cmd === "outputs_list") return [];
      return null;
    });
    const conns = Array.from({ length: 8 }, (_, i) => ({ id: `c${i}`, name: `n${i}` }));
    const { result } = renderHook(() =>
      useAllOutputs({ connections: conns, activeId: "c0", deferMs: 0 }),
    );
    await waitFor(() => expect(resolvers.size).toBe(6));
    expect(result.current.loading).toBe(true);
    await act(async () => {
      for (const id of ["c0", "c1", "c2", "c3", "c4", "c5"]) resolvers.get(id)([]);
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(resolvers.size).toBe(8));
    await act(async () => {
      for (const id of ["c6", "c7"]) resolvers.get(id)([]);
      await new Promise((r) => setTimeout(r, 20));
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
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
