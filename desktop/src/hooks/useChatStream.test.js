import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useChatStream } from "./useChatStream.js";

// `chat-event` is the only Tauri event the hook listens for. Capture the
// callback so each test can inject frames synchronously.
let chatEventCb;
let unlisten;

function emit(payload) {
  act(() => chatEventCb({ payload }));
}

function mount(extras = {}) {
  const notify = vi.fn();
  const setSessionData = vi.fn();
  const setView = vi.fn();
  const setRewriteDraft = vi.fn();
  const reload = vi.fn();
  const reloadRef = { current: reload };
  const { result } = renderHook(() => useChatStream({
    setSessionData, setView, setRewriteDraft, reloadRef, notify, ...extras,
  }));
  return { result, notify, setSessionData, setView, setRewriteDraft, reload, reloadRef };
}

function seedTurn(result, partial = {}) {
  act(() => {
    result.current.setPendingTurn({
      requestId: "req-1",
      profile: "doc",
      user: "hi",
      assistantPreview: "",
      reasoningPreview: "",
      tools: [],
      ...partial,
    });
    result.current.activeRequestIdRef.current = partial.requestId ?? "req-1";
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  chatEventCb = null;
  unlisten = vi.fn();
  listen.mockImplementation(async (name, cb) => {
    if (name === "chat-event") chatEventCb = cb;
    return unlisten;
  });
  invoke.mockReset();
  invoke.mockImplementation(async () => null);
});

afterEach(() => {
  vi.useRealTimers();
});

async function waitForListen() {
  await vi.waitFor(() => expect(chatEventCb).toBeTruthy());
}

describe("useChatStream live frames", () => {
  it("session_start pins sessionId onto the pendingTurn", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result);
    emit({ kind: "session_start", session_id: "sess-1", request_id: "req-1" });
    expect(result.current.pendingTurn.sessionId).toBe("sess-1");
  });

  it("heartbeat is a no-op (only resets the watchdog clock)", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });
    const before = { ...result.current.pendingTurn };
    emit({ kind: "heartbeat", request_id: "req-1" });
    expect(result.current.pendingTurn).toEqual(before);
  });

  it("done clears pendingTurn when there is no error", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });
    emit({ kind: "done", request_id: "req-1" });
    expect(result.current.pendingTurn).toBeNull();
  });

  it("done preserves pendingTurn when an error frame already landed", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });
    emit({ kind: "error", text: "model timeout", request_id: "req-1" });
    emit({ kind: "done", request_id: "req-1" });
    expect(result.current.pendingTurn).not.toBeNull();
    expect(result.current.pendingTurn.error).toBe("model timeout");
  });

  it("drops frames from a stale request_id (interrupted turn)", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });
    emit({ kind: "tool_start", tool_id: "t1", name: "search", request_id: "req-OLD" });
    expect(result.current.pendingTurn.tools).toHaveLength(0);
  });
});

describe("useChatStream stall watchdog", () => {
  it("skips replay while the connection is confirmed offline, resumes when it returns", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "chat_events_since") return { exists: true, events: [] };
      return null;
    });
    const connectionOnlineRef = { current: false };
    const { result } = mount({ connectionOnlineRef });
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });

    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    expect(invoke).not.toHaveBeenCalledWith(
      "chat_events_since",
      expect.anything(),
    );

    connectionOnlineRef.current = true;
    await act(async () => { await vi.advanceTimersByTimeAsync(4_000); });
    expect(invoke).toHaveBeenCalledWith(
      "chat_events_since",
      expect.objectContaining({ sessionId: "sess-1" }),
    );
  });

  it("after 10s of silence replays sidecar; on done clears pendingTurn", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "chat_events_since") {
        return {
          exists: true,
          events: [
            { frame: { event: "session_start", session_id: "sess-1" } },
            { frame: { event: "assistant_delta", text: "ok" } },
            { frame: { event: "done", session_id: "sess-1" } },
          ],
        };
      }
      if (cmd === "session_detail") return { id: "sess-1", turns: [] };
      return null;
    });
    const { result, notify } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });

    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    // Settle async invoke chain.
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(invoke).toHaveBeenCalledWith(
      "chat_events_since",
      expect.objectContaining({ profile: "doc", sessionId: "sess-1", afterSeq: 0 }),
    );
    expect(notify).toHaveBeenCalledWith(
      expect.objectContaining({ variant: "info" }),
    );
    expect(result.current.pendingTurn).toBeNull();
  });

  it("if sidecar has no done frame, watchdog does NOT clear pendingTurn", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "chat_events_since") {
        return {
          exists: true,
          events: [
            { frame: { event: "session_start", session_id: "sess-1" } },
            { frame: { event: "assistant_delta", text: "Hel" } },
          ],
        };
      }
      return null;
    });
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });

    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(invoke).toHaveBeenCalledWith("chat_events_since", expect.anything());
    expect(result.current.pendingTurn).not.toBeNull();
    // Assistant preview rebuilt from replay even though not done.
    expect(result.current.pendingTurn.assistantPreview).toBe("Hel");
  });

  it("folds inter-tool prose into reasoning, keeps the final answer as the reply", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "chat_events_since") {
        return {
          exists: true,
          events: [
            { frame: { event: "session_start", session_id: "sess-1" } },
            { frame: { event: "assistant_delta", text: "Voy a investigar." } },
            { frame: { event: "tool_start", tool_id: "t1", name: "research" } },
            { frame: { event: "tool_end", tool_id: "t1", ok: true, output: "done" } },
            { frame: { event: "assistant_delta", text: "La respuesta final." } },
          ],
        };
      }
      return null;
    });
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });

    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(result.current.pendingTurn.reasoningPreview).toBe("Voy a investigar.");
    expect(result.current.pendingTurn.assistantPreview).toBe("La respuesta final.");
  });

  it("never replays an errored turn (no recovery-toast flood)", async () => {
    const { result, notify } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1", error: "model does not support image input" });

    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(invoke).not.toHaveBeenCalledWith("chat_events_since", expect.anything());
    expect(notify).not.toHaveBeenCalled();
    expect(result.current.pendingTurn.error).toBeTruthy();
  });

  it("watchdog stays quiet if no sessionId yet (pre session_start)", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: null });

    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(invoke).not.toHaveBeenCalledWith("chat_events_since", expect.anything());
    expect(result.current.pendingTurn).not.toBeNull();
  });
});
