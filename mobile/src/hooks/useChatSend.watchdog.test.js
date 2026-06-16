import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

// Watchdog covers "WebSocket alive but bytes never arrive" — Tailscale NAT
// timeouts most often. After STALL_THRESHOLD_MS (15s) of silence on the live
// stream, the hook polls host.chat.events_since and, if the sidecar contains
// a `done` frame, completes the turn from disk.

let mockCall;
let mockCallStream;
let lastStreamHandlers;
let lastStreamHandle;

vi.mock("../lib/EndpointContext", () => ({
  useEndpoint: () => ({ call: mockCall, callStream: mockCallStream }),
}));

beforeEach(() => {
  vi.useFakeTimers();
  lastStreamHandlers = null;
  lastStreamHandle = { cancel: vi.fn() };
  mockCall = vi.fn(async () => ({ events: [] }));
  mockCallStream = vi.fn((_method, _params, handlers) => {
    lastStreamHandlers = handlers;
    return lastStreamHandle;
  });
  if (typeof globalThis.requestAnimationFrame !== "function") {
    globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0);
    globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
  }
});

afterEach(() => {
  vi.useRealTimers();
});

const { useChatSend } = await import("./useChatSend.js");

describe("useChatSend watchdog", () => {
  it("does NOT fire while frames keep arriving inside the threshold", async () => {
    const { result } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send("hi"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));

    // Heartbeat every 5s keeps lastFrameAt fresh — watchdog must stay quiet.
    for (let i = 0; i < 5; i++) {
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      act(() => lastStreamHandlers.onFrame({ event: "heartbeat" }));
    }
    expect(mockCall).not.toHaveBeenCalledWith("host.chat.events_since", expect.anything());
    expect(result.current.pendingTurn).not.toBeNull();
  });

  it("after 15s of silence polls host.chat.events_since and completes from sidecar done", async () => {
    mockCall.mockImplementation(async (method) => {
      if (method === "host.chat.events_since") {
        return {
          events: [
            { frame: { event: "session_start", session_id: "sess-1" } },
            { frame: { event: "reply", text: "ok", session_id: "sess-1" } },
            { frame: { event: "done", session_id: "sess-1" } },
          ],
        };
      }
      return {};
    });

    const onCompleted = vi.fn();
    const { result } = renderHook(() => useChatSend({ profile: "doc", onCompleted }));
    act(() => result.current.send("hi"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));

    // Cross the 15s stall threshold; watchdog polls every 2.5s so 16s is safe.
    await act(async () => { await vi.advanceTimersByTimeAsync(16000); });
    // Let the pending tryRecoverFromSidecar promise flush.
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(mockCall).toHaveBeenCalledWith(
      "host.chat.events_since",
      expect.objectContaining({ profile: "doc", session_id: "sess-1", after_seq: 0 }),
    );
    expect(onCompleted).toHaveBeenCalledWith(
      expect.objectContaining({ ok: true, recovered: true, sessionId: "sess-1" }),
    );
    expect(result.current.pendingTurn).toBeNull();
  });

  it("if sidecar replay has no done frame, keeps pendingTurn (no spurious clear)", async () => {
    mockCall.mockImplementation(async (method) => {
      if (method === "host.chat.events_since") {
        return {
          events: [
            { frame: { event: "session_start", session_id: "sess-1" } },
            { frame: { event: "assistant_delta", text: "Hel" } },
          ],
        };
      }
      return {};
    });

    const onCompleted = vi.fn();
    const { result } = renderHook(() => useChatSend({ profile: "doc", onCompleted }));
    act(() => result.current.send("hi"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));

    await act(async () => { await vi.advanceTimersByTimeAsync(16000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(mockCall).toHaveBeenCalledWith("host.chat.events_since", expect.anything());
    // Sidecar incomplete → watchdog must NOT clear the turn or call onCompleted.
    expect(onCompleted).not.toHaveBeenCalled();
    expect(result.current.pendingTurn).not.toBeNull();
    expect(result.current.pendingTurn.pending).toBe(true);
  });

  it("recovery from sidecar stamps at/duration_s from each frame's ts", async () => {
    mockCall.mockImplementation(async (method) => {
      if (method === "host.chat.events_since") {
        return {
          events: [
            { ts: 100, frame: { event: "session_start", session_id: "sess-1" } },
            { ts: 101, frame: { event: "tool_start", tool_id: "t1", name: "search" } },
            { ts: 104, frame: { event: "tool_end", tool_id: "t1", ok: true, output: "done" } },
          ],
        };
      }
      return {};
    });

    const { result } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send("hi"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));
    await act(async () => { await vi.advanceTimersByTimeAsync(16000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    const tool = result.current.pendingTurn.tools[0];
    expect(tool.at).toBe(101);
    expect(tool.duration_s).toBe(3);
  });
});
