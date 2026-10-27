import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
const busHandlers = new Set();
vi.mock("../lib/daemon-bus.js", () => ({
  subscribeDaemonEvent: (fn) => {
    busHandlers.add(fn);
    return () => busHandlers.delete(fn);
  },
}));

import { OTHER_ACTIVITY_DEBOUNCE_MS, OTHER_ACTIVITY_POLL_MS, useOtherActivity } from "./useOtherActivity.js";

const conn = (id, status = "online") => ({ id, name: id, kind: id === "local" ? "local" : "remote", status });

describe("useOtherActivity", () => {
  beforeEach(() => {
    invoke.mockReset();
  });

  it("reads the schedule of every online connection but the active one", async () => {
    invoke.mockImplementation((_cmd, { connectionId }) => Promise.resolve({ scheduled: [{ profile: "p", job_id: connectionId }] }));
    const connections = [conn("local"), conn("casa"), conn("mirai"), conn("down", "offline"), conn("off", "disabled")];
    const { result } = renderHook(() => useOtherActivity({ connections, activeId: "casa" }));
    await waitFor(() => expect(result.current).toHaveLength(2));
    expect(invoke.mock.calls.filter(([cmd]) => cmd === "activity_list").map(([, args]) => args.connectionId).sort()).toEqual(["local", "mirai"]);
    expect(result.current.map((r) => r.name).sort()).toEqual(["local", "mirai"]);
  });

  it("carries the fold and accent of each profile of that connection", async () => {
    invoke.mockImplementation((cmd) =>
      cmd === "profile_summaries"
        ? Promise.resolve([{ name: "sentinel", fold: "diamond", accent: "#123456" }, { name: "default", fold: "default", accent: null }])
        : Promise.resolve({ scheduled: [] }),
    );
    const { result } = renderHook(() => useOtherActivity({ connections: [conn("casa"), conn("mirai")], activeId: "casa" }));
    await waitFor(() => expect(result.current).toHaveLength(1));
    expect(result.current[0].folds.sentinel).toBe("diamond");
    expect(result.current[0].accents.sentinel).toBe("#123456");
  });

  it("keeps the schedule when the profiles of that connection cannot be read", async () => {
    invoke.mockImplementation((cmd) => (cmd === "profile_summaries" ? Promise.reject(new Error("x")) : Promise.resolve({ scheduled: [{ profile: "p", job_id: "j" }] })));
    const { result } = renderHook(() => useOtherActivity({ connections: [conn("casa"), conn("mirai")], activeId: "casa" }));
    await waitFor(() => expect(result.current).toHaveLength(1));
    expect(result.current[0].folds).toEqual({});
  });

  it("drops a connection that fails and keeps the others", async () => {
    invoke.mockImplementation((_cmd, { connectionId }) => (connectionId === "mirai" ? Promise.reject(new Error("-32601")) : Promise.resolve({ scheduled: [] })));
    const connections = [conn("casa"), conn("mirai"), conn("atlas")];
    const { result } = renderHook(() => useOtherActivity({ connections, activeId: "casa" }));
    await waitFor(() => expect(result.current.map((r) => r.id)).toEqual(["atlas"]));
  });

  it("keeps the last rows of a connection whose poll fails", async () => {
    vi.useFakeTimers();
    try {
      invoke.mockResolvedValue({ scheduled: [{ profile: "p", job_id: "j" }] });
      const connections = [conn("casa"), conn("mirai")];
      const { result } = renderHook(() => useOtherActivity({ connections, activeId: "casa" }));
      await vi.waitFor(() => expect(result.current).toHaveLength(1));
      invoke.mockRejectedValue(new Error("boom"));
      await vi.advanceTimersByTimeAsync(OTHER_ACTIVITY_POLL_MS);
      expect(invoke.mock.calls.filter(([cmd]) => cmd === "activity_list")).toHaveLength(2);
      expect(result.current.map((r) => r.id)).toEqual(["mirai"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("drops the cached rows of a connection that turns forbidden", async () => {
    vi.useFakeTimers();
    try {
      invoke.mockResolvedValue({ needs_you: [{ request_id: "r" }], scheduled: [] });
      const connections = [conn("casa"), conn("mirai")];
      const { result } = renderHook(() => useOtherActivity({ connections, activeId: "casa" }));
      await vi.waitFor(() => expect(result.current).toHaveLength(1));
      invoke.mockRejectedValue(new Error("forbidden"));
      await act(() => vi.advanceTimersByTimeAsync(OTHER_ACTIVITY_POLL_MS));
      expect(result.current).toEqual([]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not let a slower earlier load overwrite a newer one", async () => {
    vi.useFakeTimers();
    try {
      const pending = [];
      invoke.mockImplementation((cmd) => (cmd === "activity_list" ? new Promise((resolve) => pending.push(resolve)) : Promise.resolve([])));
      const { result } = renderHook(() => useOtherActivity({ connections: [conn("casa"), conn("mirai")], activeId: "casa" }));
      await act(() => vi.advanceTimersByTimeAsync(OTHER_ACTIVITY_POLL_MS));
      expect(pending).toHaveLength(2);
      await act(async () => {
        pending[1]({ needs_you: [{ request_id: "new" }], scheduled: [] });
        await vi.advanceTimersByTimeAsync(0);
      });
      await act(async () => {
        pending[0]({ needs_you: [], scheduled: [] });
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(result.current[0].activity.needs_you).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("reads a member connection too and marks it, since it still answers needs and running", async () => {
    invoke.mockResolvedValue({ needs_you: [{ request_id: "r" }], scheduled: [] });
    const connections = [conn("casa"), { ...conn("mirai"), role: "member" }, conn("atlas")];
    const { result } = renderHook(() => useOtherActivity({ connections, activeId: "casa" }));
    await waitFor(() => expect(result.current).toHaveLength(2));
    expect(result.current.map((r) => [r.id, r.member]).sort()).toEqual([["atlas", false], ["mirai", true]]);
    expect(result.current[0].activity.needs_you).toHaveLength(1);
  });

  it("refetches only the connection whose activity changed, after a short wait", async () => {
    vi.useFakeTimers();
    try {
      invoke.mockResolvedValue({ scheduled: [] });
      const { result } = renderHook(() => useOtherActivity({ connections: [conn("casa"), conn("mirai"), conn("atlas")], activeId: "casa" }));
      await vi.waitFor(() => expect(result.current).toHaveLength(2));
      const reads = () => invoke.mock.calls.filter(([cmd]) => cmd === "activity_list").map(([, a]) => a.connectionId);
      expect(reads()).toHaveLength(2);
      for (const fn of busHandlers) fn({ payload: { connection_id: "mirai", frame: { event: "activity.changed" } } });
      for (const fn of busHandlers) fn({ payload: { connection_id: "mirai", frame: { event: "activity.changed" } } });
      for (const fn of busHandlers) fn({ payload: { connection_id: "casa", frame: { event: "activity.changed" } } });
      for (const fn of busHandlers) fn({ payload: { connection_id: "atlas", frame: { event: "session_changed" } } });
      await vi.advanceTimersByTimeAsync(OTHER_ACTIVITY_DEBOUNCE_MS + 10);
      expect(reads().slice(2)).toEqual(["mirai"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("drops the rows of a connection that became active before the next load lands", async () => {
    invoke.mockResolvedValue({ scheduled: [] });
    const connections = [conn("casa"), conn("mirai")];
    const { result, rerender } = renderHook(({ activeId }) => useOtherActivity({ connections, activeId }), { initialProps: { activeId: "casa" } });
    await waitFor(() => expect(result.current.map((r) => r.id)).toEqual(["mirai"]));
    invoke.mockReturnValue(new Promise(() => {}));
    rerender({ activeId: "mirai" });
    expect(result.current).toEqual([]);
  });

  it("does not call the daemon when there is only the active connection", () => {
    const { result } = renderHook(() => useOtherActivity({ connections: [conn("casa")], activeId: "casa" }));
    expect(result.current).toEqual([]);
    expect(invoke).not.toHaveBeenCalled();
  });
});
