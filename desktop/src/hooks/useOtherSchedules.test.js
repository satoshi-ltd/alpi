import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { OTHER_SCHEDULES_POLL_MS, useOtherSchedules } from "./useOtherSchedules.js";

const conn = (id, status = "online") => ({ id, name: id, kind: id === "local" ? "local" : "remote", status });

describe("useOtherSchedules", () => {
  beforeEach(() => {
    invoke.mockReset();
  });

  it("reads the schedule of every online connection but the active one", async () => {
    invoke.mockImplementation((_cmd, { connectionId }) => Promise.resolve({ scheduled: [{ profile: "p", job_id: connectionId }] }));
    const connections = [conn("local"), conn("casa"), conn("mirai"), conn("down", "offline"), conn("off", "disabled")];
    const { result } = renderHook(() => useOtherSchedules({ connections, activeId: "casa" }));
    await waitFor(() => expect(result.current).toHaveLength(2));
    expect(invoke.mock.calls.map(([, args]) => args.connectionId).sort()).toEqual(["local", "mirai"]);
    expect(result.current.map((r) => r.name).sort()).toEqual(["local", "mirai"]);
  });

  it("drops a connection that fails and keeps the others", async () => {
    invoke.mockImplementation((_cmd, { connectionId }) => (connectionId === "mirai" ? Promise.reject(new Error("-32601")) : Promise.resolve({ scheduled: [] })));
    const connections = [conn("casa"), conn("mirai"), conn("atlas")];
    const { result } = renderHook(() => useOtherSchedules({ connections, activeId: "casa" }));
    await waitFor(() => expect(result.current.map((r) => r.id)).toEqual(["atlas"]));
  });

  it("keeps the last rows of a connection whose poll fails", async () => {
    vi.useFakeTimers();
    try {
      invoke.mockResolvedValue({ scheduled: [{ profile: "p", job_id: "j" }] });
      const connections = [conn("casa"), conn("mirai")];
      const { result } = renderHook(() => useOtherSchedules({ connections, activeId: "casa" }));
      await vi.waitFor(() => expect(result.current).toHaveLength(1));
      invoke.mockRejectedValue(new Error("boom"));
      await vi.advanceTimersByTimeAsync(OTHER_SCHEDULES_POLL_MS);
      expect(invoke).toHaveBeenCalledTimes(2);
      expect(result.current.map((r) => r.id)).toEqual(["mirai"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("skips a member connection, which can only answer an empty list", async () => {
    invoke.mockResolvedValue({ scheduled: [] });
    const connections = [conn("casa"), { ...conn("mirai"), role: "member" }, conn("atlas")];
    renderHook(() => useOtherSchedules({ connections, activeId: "casa" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(1));
    expect(invoke.mock.calls[0][1].connectionId).toBe("atlas");
  });

  it("drops the rows of a connection that became active before the next load lands", async () => {
    invoke.mockResolvedValue({ scheduled: [] });
    const connections = [conn("casa"), conn("mirai")];
    const { result, rerender } = renderHook(({ activeId }) => useOtherSchedules({ connections, activeId }), { initialProps: { activeId: "casa" } });
    await waitFor(() => expect(result.current.map((r) => r.id)).toEqual(["mirai"]));
    invoke.mockReturnValue(new Promise(() => {}));
    rerender({ activeId: "mirai" });
    expect(result.current).toEqual([]);
  });

  it("does not call the daemon when there is only the active connection", () => {
    const { result } = renderHook(() => useOtherSchedules({ connections: [conn("casa")], activeId: "casa" }));
    expect(result.current).toEqual([]);
    expect(invoke).not.toHaveBeenCalled();
  });
});
