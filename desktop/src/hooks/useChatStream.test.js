import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useChatStream } from "./useChatStream.js";

// `chat-event` is the only Tauri event the hook listens for. Capture the
// callback so each test can inject frames synchronously.
let chatEventCb;
let unlisten;

function emit(payload) {
  act(() => chatEventCb({ payload: { request_id: "req-1", ...payload } }));
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
  const requestId = partial.requestId ?? "req-1";
  act(() => {
    result.current.startTurn({
      requestId,
      profile: "doc",
      user: "hi",
      assistantPreview: "",
      reasoningPreview: "",
      tools: [],
      sessionId: partial.sessionId ?? null,
      launchSessionId: partial.launchSessionId ?? partial.sessionId ?? null,
      ...partial,
    });
  });
}

function turnOf(result, rid = "req-1") {
  return result.current.pendingTurns[rid] ?? null;
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
  it("session_start pins sessionId onto the turn", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result);
    emit({ kind: "session_start", session_id: "sess-1" });
    expect(turnOf(result).sessionId).toBe("sess-1");
  });

  it("heartbeat is a no-op (only resets the watchdog clock)", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });
    const before = { ...turnOf(result) };
    emit({ kind: "heartbeat" });
    expect(turnOf(result)).toEqual(before);
  });

  it("done removes the turn when there is no error", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });
    emit({ kind: "done" });
    expect(turnOf(result)).toBeNull();
  });

  it("done preserves the turn when an error frame already landed", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });
    emit({ kind: "error", text: "model timeout" });
    emit({ kind: "done" });
    expect(turnOf(result)).not.toBeNull();
    expect(turnOf(result).error).toBe("model timeout");
  });

  it("drops frames whose request_id is not a tracked turn (interrupted/stale)", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });
    emit({ kind: "tool_start", tool_id: "t1", name: "search", request_id: "req-OLD" });
    expect(turnOf(result).tools).toHaveLength(0);
  });
});

describe("useChatStream concurrent turns", () => {
  it("routes frames to the turn matching request_id; other turns are untouched", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { requestId: "req-1", sessionId: "s1" });
    seedTurn(result, { requestId: "req-2", sessionId: "s2" });
    emit({ kind: "tool_start", tool_id: "t1", name: "search", request_id: "req-1" });
    expect(turnOf(result, "req-1").tools).toHaveLength(1);
    expect(turnOf(result, "req-2").tools).toHaveLength(0);
  });

  it("done on one turn leaves the others streaming", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { requestId: "req-1", sessionId: "s1" });
    seedTurn(result, { requestId: "req-2", sessionId: "s2" });
    emit({ kind: "done", request_id: "req-1" });
    expect(turnOf(result, "req-1")).toBeNull();
    expect(turnOf(result, "req-2")).not.toBeNull();
  });

  it("deltas fan out to the right turn only", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { requestId: "req-1", sessionId: "s1" });
    seedTurn(result, { requestId: "req-2", sessionId: "s2" });
    emit({ kind: "assistant_delta", text: "for one", request_id: "req-1" });
    emit({ kind: "assistant_delta", text: "for two", request_id: "req-2" });
    await act(async () => { await vi.advanceTimersByTimeAsync(60); });
    expect(turnOf(result, "req-1").assistantPreview).toBe("for one");
    expect(turnOf(result, "req-2").assistantPreview).toBe("for two");
  });

  it("re-sending into the same chat evicts its prior turn but spares other chats", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { requestId: "req-1", sessionId: "s1", launchSessionId: "s1" });
    seedTurn(result, { requestId: "req-2", sessionId: "s2", launchSessionId: "s2" });
    // New turn launched into s1 supersedes req-1; req-2 (a different chat) is left alone.
    seedTurn(result, { requestId: "req-3", sessionId: "s1", launchSessionId: "s1" });
    expect(turnOf(result, "req-1")).toBeNull();
    expect(turnOf(result, "req-2")).not.toBeNull();
    expect(turnOf(result, "req-3")).not.toBeNull();
  });

  it("a second send from the blank composer supersedes the prior new-chat turn", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { requestId: "req-1", sessionId: null, launchSessionId: null });
    seedTurn(result, { requestId: "req-2", sessionId: null, launchSessionId: null });
    expect(turnOf(result, "req-1")).toBeNull();
    expect(turnOf(result, "req-2")).not.toBeNull();
  });

  it("a blank-composer send leaves existing-session turns alone", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { requestId: "req-1", sessionId: "s1", launchSessionId: "s1" });
    seedTurn(result, { requestId: "req-2", sessionId: null, launchSessionId: null });
    expect(turnOf(result, "req-1")).not.toBeNull();
    expect(turnOf(result, "req-2")).not.toBeNull();
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

  it("after 10s of silence replays sidecar; on done clears the turn", async () => {
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
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(invoke).toHaveBeenCalledWith(
      "chat_events_since",
      expect.objectContaining({ profile: "doc", sessionId: "sess-1", afterSeq: 0 }),
    );
    expect(notify).toHaveBeenCalledWith(
      expect.objectContaining({ variant: "info" }),
    );
    expect(turnOf(result)).toBeNull();
  });

  it("if sidecar has no done frame, watchdog does NOT clear the turn", async () => {
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
    expect(turnOf(result)).not.toBeNull();
    // Assistant preview rebuilt from replay even though not done.
    expect(turnOf(result).assistantPreview).toBe("Hel");
  });

  it("attaches inter-tool prose to the tool as its reasoning, keeps the final answer as the reply", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "chat_events_since") {
        return {
          exists: true,
          events: [
            { frame: { event: "session_start", session_id: "sess-1" } },
            { frame: { event: "assistant_delta", text: "Let me investigate." } },
            { frame: { event: "tool_start", tool_id: "t1", name: "research" } },
            { frame: { event: "tool_end", tool_id: "t1", ok: true, output: "done" } },
            { frame: { event: "assistant_delta", text: "The final answer." } },
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

    expect(turnOf(result).tools[0].reasoning).toBe("Let me investigate.");
    expect(turnOf(result).reasoningPreview).toBe("");
    expect(turnOf(result).assistantPreview).toBe("The final answer.");
  });

  it("stamps at on tool_start and duration_s on tool_end so per-step seconds show live", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });
    emit({ kind: "tool_start", tool_id: "t1", name: "search" });
    expect(typeof turnOf(result).tools[0].at).toBe("number");
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    emit({ kind: "tool_end", tool_id: "t1", ok: true, output: "done" });
    expect(turnOf(result).tools[0].duration_s).toBeGreaterThan(0);
  });

  it("replay carries at/duration_s from the sidecar ts", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "chat_events_since") {
        return {
          exists: true,
          events: [
            { ts: 100, frame: { event: "session_start", session_id: "sess-1" } },
            { ts: 101, frame: { event: "tool_start", tool_id: "t1", name: "search" } },
            { ts: 104, frame: { event: "tool_end", tool_id: "t1", ok: true, output: "done" } },
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
    expect(turnOf(result).tools[0].at).toBe(101);
    expect(turnOf(result).tools[0].duration_s).toBe(3);
  });

  it("a simple answer streams live into the answer bubble (no tool, no thinking)", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });
    emit({ kind: "assistant_delta", text: "hello there" });
    await act(async () => { await vi.advanceTimersByTimeAsync(60); });
    expect(turnOf(result).assistantPreview).toBe("hello there");
    expect(turnOf(result).reasoningPreview).toBe("");
  });

  it("never replays an errored turn (no recovery-toast flood)", async () => {
    const { result, notify } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1", error: "model does not support image input" });

    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(invoke).not.toHaveBeenCalledWith("chat_events_since", expect.anything());
    expect(notify).not.toHaveBeenCalled();
    expect(turnOf(result).error).toBeTruthy();
  });

  it("watchdog stays quiet if no sessionId yet (pre session_start)", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: null });

    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(invoke).not.toHaveBeenCalledWith("chat_events_since", expect.anything());
    expect(turnOf(result)).not.toBeNull();
  });
});
