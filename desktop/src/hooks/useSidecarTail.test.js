import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { useSidecarTail } from "./useSidecarTail.js";

beforeEach(() => {
  vi.useFakeTimers();
  invoke.mockReset();
  invoke.mockImplementation(async () => null);
});
afterEach(() => vi.useRealTimers());

describe("useSidecarTail", () => {
  it("returns null and never polls while inactive", async () => {
    const { result } = renderHook(() => useSidecarTail({ profile: "a", sessionId: "s1", active: false }));
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(result.current).toBeNull();
    expect(invoke).not.toHaveBeenCalledWith("chat_events_since", expect.anything());
  });

  it("tails the sidecar and reconstructs live progress when active", async () => {
    invoke.mockImplementation(async (cmd, args) => {
      if (cmd === "chat_events_since") {
        const after = args?.afterSeq ?? 0;
        const all = [
          { seq: 1, frame: { event: "tool_start", tool_id: "t1", name: "search" } },
          { seq: 2, frame: { event: "tool_end", tool_id: "t1", ok: true, output: "ok" } },
        ];
        return { exists: true, next_seq: 2, events: all.filter((e) => e.seq > after) };
      }
      return null;
    });
    const { result } = renderHook(() => useSidecarTail({ profile: "a", sessionId: "s1", active: true }));
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    expect(invoke).toHaveBeenCalledWith("chat_events_since", expect.objectContaining({ sessionId: "s1", afterSeq: 0 }));
    expect(result.current?.tools).toHaveLength(1);
    expect(result.current.tools[0].name).toBe("search");
  });

  it("stops fetching once the sidecar reaches done", async () => {
    invoke.mockImplementation(async (cmd, args) => {
      if (cmd === "chat_events_since") {
        const after = args?.afterSeq ?? 0;
        const all = [{ seq: 1, frame: { event: "done", session_id: "s1" } }];
        return { exists: true, next_seq: 1, events: all.filter((e) => e.seq > after) };
      }
      return null;
    });
    const { result } = renderHook(() => useSidecarTail({ profile: "a", sessionId: "s1", active: true }));
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    expect(result.current?.sawDone).toBe(true);
    const before = invoke.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(invoke.mock.calls.length).toBe(before);
  });

  it("fires onDone exactly once when the sidecar reaches done", async () => {
    const onDone = vi.fn();
    invoke.mockImplementation(async (cmd, args) => {
      if (cmd === "chat_events_since") {
        const after = args?.afterSeq ?? 0;
        const all = [
          { seq: 1, frame: { event: "tool_start", tool_id: "t1", name: "search" } },
          { seq: 2, frame: { event: "done", session_id: "s1" } },
        ];
        return { exists: true, next_seq: 2, events: all.filter((e) => e.seq > after) };
      }
      return null;
    });
    renderHook(() => useSidecarTail({ profile: "a", sessionId: "s1", active: true, onDone }));
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    expect(onDone).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("does not fire onDone while the turn is still streaming", async () => {
    const onDone = vi.fn();
    invoke.mockImplementation(async (cmd, args) => {
      if (cmd === "chat_events_since") {
        const after = args?.afterSeq ?? 0;
        const all = [{ seq: 1, frame: { event: "tool_start", tool_id: "t1", name: "search" } }];
        return { exists: true, next_seq: 1, events: all.filter((e) => e.seq > after) };
      }
      return null;
    });
    renderHook(() => useSidecarTail({ profile: "a", sessionId: "s1", active: true, onDone }));
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(onDone).not.toHaveBeenCalled();
  });
});
