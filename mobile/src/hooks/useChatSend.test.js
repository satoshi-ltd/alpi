import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

let mockCall;
let mockCallStream;
let lastStreamHandlers;
let lastStreamHandle;

vi.mock("../lib/EndpointContext", () => ({
  useEndpoint: () => ({
    call: mockCall,
    callStream: mockCallStream,
  }),
}));

// rAF in jsdom: run synchronously so deltas flush in-test.
beforeEach(() => {
  lastStreamHandlers = null;
  lastStreamHandle = { cancel: vi.fn() };
  mockCall = vi.fn(async () => ({ events: [] }));
  mockCallStream = vi.fn((method, params, handlers) => {
    lastStreamHandlers = handlers;
    return lastStreamHandle;
  });
  if (typeof globalThis.requestAnimationFrame !== "function") {
    globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0);
    globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
  }
});

// Import AFTER vi.mock so the hook gets the mocked useEndpoint.
const { useChatSend } = await import("./useChatSend.js");

describe("useChatSend.send", () => {
  it("does nothing without text or profile", () => {
    const { result } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send(""));
    expect(mockCallStream).not.toHaveBeenCalled();
  });

  it("starts a stream and exposes pendingTurn", () => {
    const { result } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send("hello"));
    expect(mockCallStream).toHaveBeenCalledTimes(1);
    const [method, params] = mockCallStream.mock.calls[0];
    expect(method).toBe("host.chat.send");
    expect(params.profile).toBe("doc");
    expect(params.text).toBe("hello");
    expect(typeof params.request_id).toBe("string");
    expect(result.current.pendingTurn.user).toBe("hello");
    expect(result.current.pendingTurn.pending).toBe(true);
  });

  it("forwards rewrite_from_turn when options.rewriteFromTurn is an integer", () => {
    const { result } = renderHook(() => useChatSend({ profile: "doc", sessionId: "s-1" }));
    act(() => result.current.send("edited text", { rewriteFromTurn: 4 }));
    const [, params] = mockCallStream.mock.calls[0];
    expect(params.rewrite_from_turn).toBe(4);
    expect(params.session_id).toBe("s-1");
  });

  it("omits rewrite_from_turn for normal sends", () => {
    const { result } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send("hello"));
    const [, params] = mockCallStream.mock.calls[0];
    expect(params).not.toHaveProperty("rewrite_from_turn");
  });

  it("ignores rewriteFromTurn when it is not an integer", () => {
    const { result } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send("hello", { rewriteFromTurn: "3" }));
    const [, params] = mockCallStream.mock.calls[0];
    expect(params).not.toHaveProperty("rewrite_from_turn");
  });

  it("session_start frame pins sessionId on pendingTurn", () => {
    const { result } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send("hi"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));
    expect(result.current.pendingTurn.sessionId).toBe("sess-1");
  });

  it("tool_start adds a tool entry; tool_end marks ok", () => {
    const { result } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send("hi"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));
    act(() =>
      lastStreamHandlers.onFrame({
        event: "tool_start", tool_id: "t1", name: "search", args: { q: "x" },
      }),
    );
    expect(result.current.pendingTurn.tools).toHaveLength(1);
    expect(result.current.pendingTurn.tools[0]).toMatchObject({ tool_id: "t1", name: "search", ok: null });
    act(() =>
      lastStreamHandlers.onFrame({ event: "tool_end", tool_id: "t1", ok: true, output: "ok" }),
    );
    expect(result.current.pendingTurn.tools[0]).toMatchObject({ tool_id: "t1", ok: true, output: "ok" });
  });

  it("onDone calls onCompleted({ok:true}) and clears pendingTurn", async () => {
    const onCompleted = vi.fn();
    const { result } = renderHook(() => useChatSend({ profile: "doc", onCompleted }));
    act(() => result.current.send("hi"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));
    await act(async () => {
      await lastStreamHandlers.onDone();
    });
    expect(onCompleted).toHaveBeenCalledWith(
      expect.objectContaining({ ok: true, sessionId: "sess-1" }),
    );
    expect(result.current.pendingTurn).toBeNull();
  });

  it("cancel cancels the stream handle and clears pendingTurn", () => {
    const { result } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send("hi"));
    act(() => result.current.cancel());
    expect(lastStreamHandle.cancel).toHaveBeenCalled();
    expect(result.current.pendingTurn).toBeNull();
  });

  it("unmount detaches but does NOT cancel — daemon work survives screen exit", () => {
    lastStreamHandle = { cancel: vi.fn(), detach: vi.fn() };
    const { result, unmount } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send("research awake"));
    unmount();
    expect(lastStreamHandle.detach).toHaveBeenCalledTimes(1);
    expect(lastStreamHandle.cancel).not.toHaveBeenCalled();
  });

  it("onError recovers from sidecar when host.chat.events_since contains done", async () => {
    mockCall.mockResolvedValueOnce({
      events: [
        { frame: { event: "session_start", session_id: "sess-1" } },
        { frame: { event: "assistant_delta", text: "Hello" } },
        { frame: { event: "reply", text: "Hello world", session_id: "sess-1" } },
        { frame: { event: "done", session_id: "sess-1" } },
      ],
    });
    const onCompleted = vi.fn();
    const { result } = renderHook(() => useChatSend({ profile: "doc", onCompleted }));
    act(() => result.current.send("hi"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));
    await act(async () => {
      await lastStreamHandlers.onError(new Error("ws died"));
    });
    expect(mockCall).toHaveBeenCalledWith(
      "host.chat.events_since",
      expect.objectContaining({ profile: "doc", session_id: "sess-1" }),
    );
    expect(onCompleted).toHaveBeenCalledWith(
      expect.objectContaining({ ok: true, recovered: true, sessionId: "sess-1" }),
    );
    expect(result.current.pendingTurn).toBeNull();
  });

  it("onError surfaces the partial preview + error when sidecar has no done", async () => {
    mockCall.mockResolvedValueOnce({
      events: [
        { frame: { event: "session_start", session_id: "sess-1" } },
        { frame: { event: "assistant_delta", text: "Hel" } },
      ],
    });
    const onCompleted = vi.fn();
    const { result } = renderHook(() => useChatSend({ profile: "doc", onCompleted }));
    act(() => result.current.send("hi"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));
    await act(async () => {
      await lastStreamHandlers.onError(new Error("ws died"));
    });
    expect(onCompleted).toHaveBeenCalledWith(
      expect.objectContaining({ ok: false }),
    );
    expect(result.current.pendingTurn.error).toMatch(/ws died/);
    expect(result.current.pendingTurn.pending).toBe(false);
  });

  it("onError leaves preview untouched when sidecar returns empty (defensive)", async () => {
    mockCall.mockResolvedValueOnce({ events: [] });
    const { result } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send("hi"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));
    // `reply` sets assistant synchronously (assistant_delta goes through rAF, which jsdom doesn't tick reliably).
    act(() => lastStreamHandlers.onFrame({ event: "reply", text: "partial reply" }));
    expect(result.current.pendingTurn.assistant).toBe("partial reply");
    await act(async () => {
      await lastStreamHandlers.onError(new Error("ws died"));
    });
    // Assistant preview was NOT wiped — sidecar was empty, so we kept what we had.
    expect(result.current.pendingTurn.assistant).toBe("partial reply");
    expect(result.current.pendingTurn.error).toMatch(/ws died/);
  });

  it("attaches inter-tool prose to the tool as its reasoning, keeps the final answer separate", () => {
    const { result } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send("hi"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));
    act(() => lastStreamHandlers.onFrame({ event: "assistant_delta", text: "Let me investigate." }));
    act(() => lastStreamHandlers.onFrame({ event: "tool_start", tool_id: "t1", name: "research" }));
    expect(result.current.pendingTurn.tools[0].reasoning).toBe("Let me investigate.");
    expect(result.current.pendingTurn.reasoning).toBe("");
    expect(result.current.pendingTurn.assistant).toBe("");
    act(() => lastStreamHandlers.onFrame({ event: "reply", text: "The answer." }));
    expect(result.current.pendingTurn.assistant).toBe("The answer.");
    expect(result.current.pendingTurn.tools[0].reasoning).toBe("Let me investigate.");
  });

  it("stamps at on tool_start and duration_s on tool_end so per-step seconds show live", () => {
    const { result } = renderHook(() => useChatSend({ profile: "doc" }));
    act(() => result.current.send("hi"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));
    act(() => lastStreamHandlers.onFrame({ event: "tool_start", tool_id: "t1", name: "search" }));
    expect(typeof result.current.pendingTurn.tools[0].at).toBe("number");
    act(() => lastStreamHandlers.onFrame({ event: "tool_end", tool_id: "t1", ok: true, output: "done" }));
    expect(result.current.pendingTurn.tools[0].duration_s).toBeGreaterThanOrEqual(0);
  });
});
