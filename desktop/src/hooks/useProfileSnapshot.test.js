import { renderHook, act, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: (...a) => invokeMock(...a) }));

let busHandlers;
vi.mock("../lib/daemon-bus.js", () => ({
  subscribeDaemonEvent: (fn) => { busHandlers.add(fn); return () => busHandlers.delete(fn); },
}));

import { useProfileSnapshot, _clearProfileSnapshotCache } from "./useProfileSnapshot.js";

function emit(payload) {
  for (const fn of Array.from(busHandlers)) fn({ payload });
}

beforeEach(() => {
  busHandlers = new Set();
  invokeMock.mockReset();
  _clearProfileSnapshotCache();
});

describe("useProfileSnapshot", () => {
  it("fetches the snapshot for the (connection, profile)", async () => {
    invokeMock.mockResolvedValue({ detail: { models: ["a/b"] } });
    const { result } = renderHook(() => useProfileSnapshot("c1", "doc"));
    await waitFor(() => expect(result.current.snapshot?.detail.models).toEqual(["a/b"]));
    expect(invokeMock).toHaveBeenCalledWith("settings_profile_snapshot", {
      profile: "doc", connectionId: "c1",
    });
  });

  it("serves the cached snapshot immediately on remount, then refreshes", async () => {
    invokeMock
      .mockResolvedValueOnce({ detail: { v: 1 } })
      .mockResolvedValueOnce({ detail: { v: 2 } });
    const first = renderHook(() => useProfileSnapshot("c1", "doc"));
    await waitFor(() => expect(first.result.current.snapshot.detail.v).toBe(1));
    first.unmount();

    const second = renderHook(() => useProfileSnapshot("c1", "doc"));
    expect(second.result.current.snapshot.detail.v).toBe(1);
    await waitFor(() => expect(second.result.current.snapshot.detail.v).toBe(2));
  });

  it("keeps the cached snapshot when a refresh fails transiently", async () => {
    invokeMock
      .mockResolvedValueOnce({ detail: { v: 1 } })
      .mockRejectedValueOnce(new Error("read timeout"));
    const first = renderHook(() => useProfileSnapshot("c1", "doc"));
    await waitFor(() => expect(first.result.current.snapshot.detail.v).toBe(1));
    first.unmount();

    const second = renderHook(() => useProfileSnapshot("c1", "doc"));
    await waitFor(() => expect(second.result.current.error).toBeTruthy());
    expect(second.result.current.snapshot.detail.v).toBe(1);
  });

  it("drops the snapshot on auth-failed", async () => {
    invokeMock
      .mockResolvedValueOnce({ detail: { v: 1 } })
      .mockRejectedValueOnce(new Error("alp -32000: auth-failed"));
    const first = renderHook(() => useProfileSnapshot("c1", "doc"));
    await waitFor(() => expect(first.result.current.snapshot.detail.v).toBe(1));
    first.unmount();

    const second = renderHook(() => useProfileSnapshot("c1", "doc"));
    await waitFor(() => expect(second.result.current.snapshot).toBeNull());
  });

  it("coalesces relevant daemon events into one refetch and ignores other profiles", async () => {
    vi.useFakeTimers();
    try {
      invokeMock.mockResolvedValue({ detail: { v: 1 } });
      renderHook(() => useProfileSnapshot("c1", "doc"));
      await vi.advanceTimersByTimeAsync(0);
      const before = invokeMock.mock.calls.length;

      act(() => emit({ connection_id: "c1", frame: { event: "config_changed", data: { profile: "other" } } }));
      act(() => emit({ connection_id: "c1", frame: { event: "config_changed", data: { profile: "doc" } } }));
      act(() => emit({ connection_id: "c1", frame: { event: "schedule.changed", data: { profile: "doc" } } }));
      await vi.advanceTimersByTimeAsync(300);

      expect(invokeMock.mock.calls.length).toBe(before + 1);
    } finally {
      vi.useRealTimers();
    }
  });
});
