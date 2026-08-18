import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

let mockCall;
let mockCallStream;
let lastStreamHandlers;
let streamHandles;

vi.mock("../lib/EndpointContext", () => ({
  useEndpoint: () => ({ call: mockCall, callStream: mockCallStream }),
}));

beforeEach(() => {
  vi.useFakeTimers();
  lastStreamHandlers = null;
  streamHandles = [];
  mockCall = vi.fn(async () => ({ events: [] }));
  mockCallStream = vi.fn((_method, _params, handlers) => {
    lastStreamHandlers = handlers;
    const handle = { cancel: vi.fn(), detach: vi.fn() };
    streamHandles.push(handle);
    return handle;
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

const DONE_REPLAY = {
  events: [
    { frame: { event: "reply", text: "old answer", session_id: "sess-1" } },
    { frame: { event: "done", session_id: "sess-1" } },
  ],
};

describe("useChatSend stale-turn guards", () => {
  it("a stale continuation never clears the turn that replaced it, and that turn keeps streaming", async () => {
    let releaseCompleted;
    const onCompleted = vi.fn(() => new Promise((r) => { releaseCompleted = r; }));
    const { result } = renderHook(() => useChatSend({ profile: "doc", onCompleted }));

    act(() => result.current.send("first"));
    const handlersA = lastStreamHandlers;
    act(() => handlersA.onFrame({ event: "session_start", session_id: "sess-1" }));
    act(() => handlersA.onFrame({ event: "reply", text: "first answer" }));
    let doneA;
    act(() => { doneA = handlersA.onDone(); });

    act(() => result.current.send("second"));
    const handlersB = lastStreamHandlers;
    expect(result.current.pendingTurn.user).toBe("second");

    await act(async () => {
      releaseCompleted(true);
      await doneA;
    });

    expect(result.current.pendingTurn).not.toBeNull();
    expect(result.current.pendingTurn.user).toBe("second");
    expect(result.current.pendingTurn.pending).toBe(true);

    act(() => handlersB.onFrame({ event: "session_start", session_id: "sess-1" }));
    act(() => handlersB.onFrame({ event: "reply", text: "second answer" }));
    expect(result.current.pendingTurn.assistant).toBe("second answer");
  });

  it("a stale continuation's error lands on its own turn, never on the newer one", async () => {
    let releaseCompleted;
    const onCompleted = vi.fn(() => new Promise((r) => { releaseCompleted = r; }));
    const { result } = renderHook(() => useChatSend({ profile: "doc", onCompleted }));

    act(() => result.current.send("first"));
    const handlersA = lastStreamHandlers;
    act(() => handlersA.onFrame({ event: "session_start", session_id: "sess-1" }));
    let doneA;
    act(() => { doneA = handlersA.onDone(); });

    act(() => result.current.send("second"));
    const handlersB = lastStreamHandlers;
    await act(async () => {
      releaseCompleted(true);
      await doneA;
    });

    await act(async () => { await handlersB.onError(new Error("ws died")); });
    expect(result.current.pendingTurn.user).toBe("second");
    expect(result.current.pendingTurn.error).toMatch(/ws died/);
    expect(result.current.pendingTurn.pending).toBe(false);
  });

  it("two stale settles in a row never clear the turn on screen", async () => {
    const releases = [];
    const onCompleted = vi.fn(() => new Promise((r) => { releases.push(r); }));
    const { result } = renderHook(() => useChatSend({ profile: "doc", onCompleted }));

    act(() => result.current.send("first"));
    const handlersA = lastStreamHandlers;
    act(() => handlersA.onFrame({ event: "reply", text: "first answer" }));
    let doneA;
    act(() => { doneA = handlersA.onDone(); });
    act(() => result.current.send("second"));

    const handlersB = lastStreamHandlers;
    act(() => handlersB.onFrame({ event: "reply", text: "second answer" }));
    let doneB;
    act(() => { doneB = handlersB.onDone(); });
    act(() => result.current.send("third"));

    await act(async () => {
      releases[0](false);
      releases[1](true);
      await doneA;
      await doneB;
    });
    expect(result.current.pendingTurn.user).toBe("third");
    expect(result.current.pendingTurn.pending).toBe(true);
  });

  it("a cancel that settles after the next send never clears the new turn", async () => {
    let release;
    const onCompleted = vi.fn(() => new Promise((r) => { release = r; }));
    const { result } = renderHook(() => useChatSend({ profile: "doc", onCompleted }));

    act(() => result.current.send("first"));
    act(() => lastStreamHandlers.onFrame({ event: "reply", text: "partial" }));
    act(() => result.current.cancel());
    expect(result.current.pendingTurn.assistant).toBe("partial");

    act(() => result.current.send("second"));
    await act(async () => {
      release(true);
      await Promise.resolve();
    });
    expect(result.current.pendingTurn.user).toBe("second");
    expect(result.current.pendingTurn.pending).toBe(true);
  });

  it("stale onError with an empty sidecar does not stamp its error on the newer turn", async () => {
    let resolveReplay;
    mockCall.mockImplementationOnce(() => new Promise((r) => { resolveReplay = r; }));
    const onCompleted = vi.fn();
    const { result } = renderHook(() => useChatSend({ profile: "doc", onCompleted }));

    act(() => result.current.send("first"));
    const handlersA = lastStreamHandlers;
    act(() => handlersA.onFrame({ event: "session_start", session_id: "sess-1" }));
    let errorSettled;
    act(() => { errorSettled = handlersA.onError(new Error("ws died")); });

    act(() => result.current.send("second"));
    const handlersB = lastStreamHandlers;
    const handleB = streamHandles[1];
    act(() => handlersB.onFrame({ event: "session_start", session_id: "sess-2" }));

    await act(async () => {
      resolveReplay({ events: [] });
      await errorSettled;
    });

    expect(result.current.pendingTurn).not.toBeNull();
    expect(result.current.pendingTurn.user).toBe("second");
    expect(result.current.pendingTurn.pending).toBe(true);
    expect(result.current.pendingTurn.error).toBeUndefined();
    expect(onCompleted).not.toHaveBeenCalled();
    expect(handleB.cancel).not.toHaveBeenCalled();

    act(() => handlersB.onFrame({ event: "reply", text: "new answer" }));
    expect(result.current.pendingTurn.assistant).toBe("new answer");

    act(() => result.current.cancel());
    expect(handleB.cancel).toHaveBeenCalledTimes(1);
  });

  it("stale onError recovering a done sidecar does not complete the newer turn", async () => {
    let resolveReplay;
    mockCall.mockImplementationOnce(() => new Promise((r) => { resolveReplay = r; }));
    const onCompleted = vi.fn();
    const { result } = renderHook(() => useChatSend({ profile: "doc", onCompleted }));

    act(() => result.current.send("first"));
    const handlersA = lastStreamHandlers;
    act(() => handlersA.onFrame({ event: "session_start", session_id: "sess-1" }));
    let errorSettled;
    act(() => { errorSettled = handlersA.onError(new Error("ws died")); });

    act(() => result.current.send("second"));
    const handlersB = lastStreamHandlers;
    const handleB = streamHandles[1];
    act(() => handlersB.onFrame({ event: "session_start", session_id: "sess-2" }));

    await act(async () => {
      resolveReplay(DONE_REPLAY);
      await errorSettled;
    });

    expect(result.current.pendingTurn).not.toBeNull();
    expect(result.current.pendingTurn.user).toBe("second");
    expect(result.current.pendingTurn.assistant).toBe("");
    expect(result.current.pendingTurn.pending).toBe(true);
    expect(onCompleted).not.toHaveBeenCalled();
    expect(handleB.cancel).not.toHaveBeenCalled();
  });

  it("stale watchdog recovery of a done sidecar does not complete the newer turn", async () => {
    let resolveReplay;
    mockCall.mockImplementationOnce(() => new Promise((r) => { resolveReplay = r; }));
    const onCompleted = vi.fn();
    const { result } = renderHook(() => useChatSend({ profile: "doc", onCompleted }));

    act(() => result.current.send("first"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));
    await act(async () => { await vi.advanceTimersByTimeAsync(16000); });
    expect(mockCall).toHaveBeenCalledTimes(1);

    act(() => result.current.send("second"));
    const handlersB = lastStreamHandlers;
    const handleB = streamHandles[1];
    act(() => handlersB.onFrame({ event: "session_start", session_id: "sess-2" }));

    await act(async () => {
      resolveReplay(DONE_REPLAY);
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.pendingTurn).not.toBeNull();
    expect(result.current.pendingTurn.user).toBe("second");
    expect(result.current.pendingTurn.pending).toBe(true);
    expect(onCompleted).not.toHaveBeenCalled();
    expect(handleB.cancel).not.toHaveBeenCalled();
  });

  it("a stale replay settling does not push the newer turn's stall pivot", async () => {
    let resolveReplay;
    mockCall.mockImplementationOnce(() => new Promise((r) => { resolveReplay = r; }));
    const { result } = renderHook(() => useChatSend({ profile: "doc" }));

    act(() => result.current.send("first"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-1" }));
    await act(async () => { await vi.advanceTimersByTimeAsync(16000); });

    act(() => result.current.send("second"));
    act(() => lastStreamHandlers.onFrame({ event: "session_start", session_id: "sess-2" }));

    await act(async () => { await vi.advanceTimersByTimeAsync(14000); });
    await act(async () => {
      resolveReplay({ events: [] });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(mockCall).toHaveBeenCalledTimes(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(mockCall).toHaveBeenCalledWith(
      "host.chat.events_since",
      expect.objectContaining({ profile: "doc", session_id: "sess-2", after_seq: 0 }),
    );
  });
});
