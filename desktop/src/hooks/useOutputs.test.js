import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { useMarkAllOutputsRead, useOutput, useOutputs } from "./useOutputs.js";


let daemonEventListener;
beforeEach(() => {
  vi.resetAllMocks();
  daemonEventListener = null;
  listen.mockImplementation(async (eventName, cb) => {
    if (eventName === "daemon-event") daemonEventListener = cb;
    return () => {};
  });
});


describe("useOutputs", () => {
  it("fans out one outputs_list call per profile and merges newest-first", async () => {
    invoke.mockImplementation(async (_cmd, params) => {
      if (params.profile === "abby") {
        return [
          { id: "a1", profile: "abby", created_at: 100, body: "a1", status: "unread" },
          { id: "a2", profile: "abby", created_at: 300, body: "a2", status: "unread" },
        ];
      }
      if (params.profile === "vera") {
        return [{ id: "v1", profile: "vera", created_at: 200, body: "v1", status: "unread" }];
      }
      return [];
    });
    const { result } = renderHook(() =>
      useOutputs({ profiles: [{ name: "abby" }, { name: "vera" }], connectionId: "c1", status: "unread" }),
    );
    await waitFor(() => expect(result.current.rows.length).toBe(3));
    expect(result.current.rows.map((r) => r.id)).toEqual(["a2", "v1", "a1"]);
    expect(invoke).toHaveBeenCalledWith("outputs_list", {
      profile: "abby", status: "unread", limit: 100,
    });
  });

  it("survives a per-profile failure: other profiles still surface", async () => {
    invoke.mockImplementation(async (_cmd, params) => {
      if (params.profile === "broken") throw new Error("auth-failed");
      return [{ id: "ok-" + params.profile, profile: params.profile, created_at: 1, status: "unread" }];
    });
    const { result } = renderHook(() =>
      useOutputs({ profiles: [{ name: "abby" }, { name: "broken" }, { name: "vera" }], connectionId: "c1" }),
    );
    await waitFor(() => expect(result.current.rows.length).toBe(2));
    expect(result.current.rows.map((r) => r.profile).sort()).toEqual(["abby", "vera"]);
  });

  it("refreshes on the output.updated daemon event so cross-client mark_read reaches this surface", async () => {
    let listCalls = 0;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "outputs_list") {
        listCalls += 1;
        return [];
      }
      return null;
    });
    renderHook(() => useOutputs({ profiles: [{ name: "abby" }], connectionId: "c1" }));
    await waitFor(() => expect(listCalls).toBe(1));
    await waitFor(() => expect(daemonEventListener).not.toBeNull());

    await act(async () => {
      daemonEventListener({
        payload: { connection_id: "c1", frame: { event: "output.updated", data: { profile: "abby", id: "abc", status: "read" } } },
      });
    });
    await waitFor(() => expect(listCalls).toBe(2));
  });

  it("ignores output.updated from a different connection so foreign daemons don't trigger spurious fetches", async () => {
    let listCalls = 0;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "outputs_list") {
        listCalls += 1;
        return [];
      }
      return null;
    });
    renderHook(() => useOutputs({ profiles: [{ name: "abby" }], connectionId: "c1" }));
    await waitFor(() => expect(listCalls).toBe(1));
    await waitFor(() => expect(daemonEventListener).not.toBeNull());

    await act(async () => {
      daemonEventListener({
        payload: { connection_id: "c2", frame: { event: "output.updated", data: { profile: "abby" } } },
      });
    });
    await new Promise((r) => setTimeout(r, 20));
    expect(listCalls).toBe(1);
  });

  it("clears rows immediately when profiles list goes empty — no flicker of stale state on logout/disconnect", async () => {
    invoke.mockResolvedValue([{ id: "a1", profile: "abby", created_at: 1, status: "unread" }]);
    const { result, rerender } = renderHook(
      ({ profiles }) => useOutputs({ profiles, connectionId: "c1" }),
      { initialProps: { profiles: [{ name: "abby" }] } },
    );
    await waitFor(() => expect(result.current.rows.length).toBe(1));
    rerender({ profiles: [] });
    await waitFor(() => expect(result.current.rows).toEqual([]));
  });
});


describe("local pub/sub after mutations", () => {
  it("markRead in one hook refreshes every mounted useOutputs — keeps modal rows + sidebar badge in sync", async () => {
    let listCalls = 0;
    invoke.mockImplementation(async (cmd, params) => {
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
    const list = renderHook(() => useOutputs({ profiles: [{ name: "abby" }], connectionId: "c1" }));
    const detail = renderHook(() => useOutput("abby", "abc123"));
    await waitFor(() => expect(list.result.current.rows.length).toBe(1));
    await waitFor(() => expect(detail.result.current.row?.status).toBe("unread"));
    const before = listCalls;

    await act(async () => {
      await detail.result.current.markRead();
    });

    await waitFor(() => expect(listCalls).toBeGreaterThan(before));
  });

  it("mark_all_read with count > 0 refreshes all mounted useOutputs; zero-count run does NOT", async () => {
    let listCalls = 0;
    let nextCount = 5;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "outputs_list") {
        listCalls += 1;
        return [];
      }
      if (cmd === "outputs_mark_all_read") {
        return nextCount;
      }
      return null;
    });
    renderHook(() => useOutputs({ profiles: [{ name: "abby" }], connectionId: "c1" }));
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
