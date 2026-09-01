import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { readFileSync } from "node:fs";
import { join } from "node:path";
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
  const { result, unmount } = renderHook(() => useChatStream({
    setSessionData, setView, setRewriteDraft, reloadRef, notify, ...extras,
  }));
  return { result, unmount, notify, setSessionData, setView, setRewriteDraft, reload, reloadRef };
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

async function settle(ms = 0) {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
}

describe("useChatStream live frames", () => {
  it("session_start pins sessionId onto the turn", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result);
    emit({ kind: "session_start", session_id: "sess-1" });
    expect(turnOf(result).sessionId).toBe("sess-1");
  });

  it("usage frames track only completions that update the chat context", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result);
    emit({ kind: "usage", tokens_in: 42000, context_tokens: 42000 });
    expect(turnOf(result).ctxTokens).toBe(42000);
    emit({ kind: "usage", tokens_in: 55000, context_tokens: 55000 });
    expect(turnOf(result).ctxTokens).toBe(55000);
    emit({ kind: "usage", tokens_in: 8000, context_tokens: 0, model: "vision-side-call" });
    expect(turnOf(result).ctxTokens).toBe(55000);
  });

  it("auto-compaction replaces the live context with its reduced size", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { ctxTokens: 180000 });
    emit({ kind: "auto_compact", text: "compacted", tokens_before: 180000, tokens_after: 90000 });
    expect(turnOf(result).ctxTokens).toBe(90000);
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
    seedTurn(result, { connectionId: "A", sessionId: "sess-1" });
    emit({ kind: "done" });
    await settle();
    expect(turnOf(result)).toBeNull();
  });

  it("done loads the finished transcript when reply was never seen", async () => {
    const { result, setSessionData } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    invoke.mockClear();
    setSessionData.mockClear();
    emit({ kind: "done", session_id: "sess-1" });
    expect(invoke.mock.calls.some(([cmd]) => cmd === "session_detail")).toBe(true);
    await settle();
    expect(turnOf(result)).toBeNull();
  });

  it("done does not re-load the transcript when reply already loaded it", async () => {
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    invoke.mockClear();
    emit({ kind: "reply", session_id: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await settle();
    const detailCalls = invoke.mock.calls.filter(([cmd]) => cmd === "session_detail").length;
    expect(detailCalls).toBe(1);
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
    await settle();
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

  it("does not evict a same-profile turn that belongs to another connection", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { requestId: "req-1", connectionId: "A", sessionId: "s1", launchSessionId: "s1" });
    seedTurn(result, { requestId: "req-2", connectionId: "B", sessionId: "s1", launchSessionId: "s1" });
    expect(turnOf(result, "req-1")).not.toBeNull();
    expect(turnOf(result, "req-2")).not.toBeNull();
  });
});

describe("useChatStream completed-turn seam", () => {
  function deferredDetail() {
    let settle;
    invoke.mockImplementation((cmd) => {
      if (cmd === "session_detail") return new Promise((res, rej) => { settle = { res, rej }; });
      return Promise.resolve(null);
    });
    return () => settle;
  }

  it("keeps the completed turn on screen until the reply's fetch has been applied", async () => {
    const pending = deferredDetail();
    const { result, reload } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "reply", session_id: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await settle();

    expect(turnOf(result)).not.toBeNull();
    expect(reload).not.toHaveBeenCalled();
    expect(invoke.mock.calls.filter(([cmd]) => cmd === "session_detail")).toHaveLength(1);

    await act(async () => {
      pending().res({ id: "sess-1", turns: [] });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(turnOf(result)).toBeNull();
    expect(reload).toHaveBeenCalled();
  });

  it("drops the turn when the transcript fetch fails, degrading to the pre-wait behaviour", async () => {
    const pending = deferredDetail();
    const { result, notify } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "reply", session_id: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await act(async () => {
      pending().rej(new Error("connection-disabled"));
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(turnOf(result)).toBeNull();
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ variant: "error" }));
  });

  it("drops the turn when done's own fetch fails, never stranding it with a fabricated error", async () => {
    const pending = deferredDetail();
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await act(async () => {
      pending().rej(new Error("-32004 session-not-found"));
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(turnOf(result)).toBeNull();
  });

  it("degrades to a plain drop when the transport answers nothing inside the bound", async () => {
    deferredDetail();
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "reply", session_id: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });

    await settle(29_000);
    expect(turnOf(result)).not.toBeNull();
    expect(turnOf(result).error).toBeFalsy();

    await settle(2_000);
    expect(turnOf(result)).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
    expect(invoke.mock.calls.filter(([cmd]) => cmd === "session_detail")).toHaveLength(1);
  });

  it("a transcript that lands after the bound is still applied, and strands nothing", async () => {
    const pending = deferredDetail();
    const { result, reload } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "reply", session_id: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await settle(31_000);
    expect(turnOf(result)).toBeNull();

    await act(async () => {
      pending().res({ id: "sess-1", turns: [{ user: "hi", assistant: "there" }] });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(turnOf(result)).toBeNull();
    expect(reload).toHaveBeenCalled();
  });

  it("a rejection after the bound leaves no stranded turn either", async () => {
    const pending = deferredDetail();
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await settle(31_000);

    await act(async () => {
      pending().rej(new Error("connection-disabled"));
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(turnOf(result)).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("marks the turn settling while its transcript read is outstanding", async () => {
    const pending = deferredDetail();
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await settle();
    expect(turnOf(result).settling).toBe(true);

    await act(async () => {
      pending().res({ id: "sess-1", turns: [] });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(turnOf(result)).toBeNull();
  });

  it("marks the turn settling only while the read is outstanding, then drops it on failure", async () => {
    const pending = deferredDetail();
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await act(async () => {
      pending().rej(new Error("connection-disabled"));
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(turnOf(result)).toBeNull();
  });

  it("never invents a turn state the pre-wait code could not produce", () => {
    const src = readFileSync(join(import.meta.dirname, "useChatStream.js"), "utf8");
    expect(src).not.toMatch(/TRANSCRIPT_LOAD_FAILED|flagLoadFailure/);
    expect(src).not.toMatch(/did not load/);
    const settle = src.slice(src.indexOf("const settleTurn"), src.indexOf("const settleTurn") + 1200);
    expect(settle.match(/dropSettledTurn\(requestId\)/g)).toHaveLength(3);
    expect(settle).not.toMatch(/error:/);
  });

  it("a duplicate done inside the settle window neither refetches nor re-arms the wait", async () => {
    const pending = deferredDetail();
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await settle();
    emit({ kind: "done", session_id: "sess-1" });
    await settle();

    expect(invoke.mock.calls.filter(([cmd]) => cmd === "session_detail")).toHaveLength(1);

    await act(async () => {
      pending().res({ id: "sess-1", turns: [] });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(turnOf(result)).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("an error frame arriving inside the settle window does not pin the finished turn", async () => {
    const pending = deferredDetail();
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await settle();
    emit({ kind: "error", text: "model timeout" });
    expect(turnOf(result).error).toBeFalsy();

    await act(async () => {
      pending().res({ id: "sess-1", turns: [] });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(turnOf(result)).toBeNull();
  });

  it("a settle that resolves after its request id was reused leaves the new turn alone", async () => {
    const pending = deferredDetail();
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { requestId: "req-1", connectionId: "A", profile: "doc", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await settle();
    seedTurn(result, { requestId: "req-1", connectionId: "A", profile: "lens", sessionId: "sess-9", launchSessionId: "sess-9" });

    await act(async () => {
      pending().res({ id: "sess-1", turns: [] });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(turnOf(result, "req-1")).not.toBeNull();
    expect(turnOf(result, "req-1").profile).toBe("lens");
    expect(turnOf(result, "req-1").error).toBeFalsy();
    expect(turnOf(result, "req-1").settling).toBeFalsy();

    await settle(40_000);
    expect(turnOf(result, "req-1")).not.toBeNull();
  });

  it("does not flag a turn whose fetch resolves inside the bound", async () => {
    const pending = deferredDetail();
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "reply", session_id: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await act(async () => {
      pending().res({ id: "sess-1", turns: [] });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(turnOf(result)).toBeNull();

    await settle(40_000);
    expect(turnOf(result)).toBeNull();
  });

  it("an error frame before done keeps the turn and skips the transcript load", async () => {
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    invoke.mockClear();
    emit({ kind: "error", text: "model timeout" });
    emit({ kind: "done", session_id: "sess-1" });
    await settle();

    expect(invoke.mock.calls.some(([cmd]) => cmd === "session_detail")).toBe(false);
    expect(turnOf(result).error).toBe("model timeout");
  });

  it("a fetch that lands after an error frame leaves the error text intact", async () => {
    const pending = deferredDetail();
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "reply", session_id: "sess-1" });
    emit({ kind: "error", text: "model timeout" });
    emit({ kind: "done", session_id: "sess-1" });
    await act(async () => {
      pending().res({ id: "sess-1", turns: [] });
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(turnOf(result).error).toBe("model timeout");
    expect(turnOf(result).settling).toBe(false);
  });

  it("removes a completed turn from another connection at once — there is nothing to await", async () => {
    const { result } = mount({ activeConnectionIdRef: { current: "B" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-A", launchSessionId: "sess-A" });
    invoke.mockClear();
    emit({ kind: "done", session_id: "sess-A" });

    expect(turnOf(result)).toBeNull();
    expect(invoke.mock.calls.some(([cmd]) => cmd === "session_detail")).toBe(false);
  });

  it("a settle wait pending on unmount leaves no live timer behind", async () => {
    deferredDetail();
    const { result, unmount } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "reply", session_id: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await settle();
    act(() => unmount());

    expect(vi.getTimerCount()).toBe(0);
  });

  it("a superseding send cancels the prior turn's settle wait", async () => {
    deferredDetail();
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { requestId: "req-1", connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });
    emit({ kind: "reply", session_id: "sess-1" });
    emit({ kind: "done", session_id: "sess-1" });
    await settle();
    seedTurn(result, { requestId: "req-2", connectionId: "A", sessionId: "sess-1", launchSessionId: "sess-1" });

    await settle(40_000);
    expect(turnOf(result, "req-1")).toBeNull();
    expect(turnOf(result, "req-2").error).toBeFalsy();
  });
});

describe("useChatStream connection scoping", () => {
  it("clearTurnsForConnection removes only the given connection's turns", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { requestId: "a1", connectionId: "A", sessionId: "s1", launchSessionId: "s1" });
    seedTurn(result, { requestId: "b1", connectionId: "B", sessionId: "s2", launchSessionId: "s2" });
    act(() => result.current.clearTurnsForConnection("A"));
    expect(turnOf(result, "a1")).toBeNull();
    expect(turnOf(result, "b1")).not.toBeNull();
  });

  it("ignores a reply for a turn on a non-active connection (no wrong-daemon fetch)", async () => {
    const { result } = mount({ activeConnectionIdRef: { current: "B" } });
    await waitForListen();
    seedTurn(result, { requestId: "req-1", connectionId: "A", sessionId: "sA", launchSessionId: "sA" });
    invoke.mockClear();
    emit({ kind: "reply", session_id: "sA" });
    expect(invoke.mock.calls.some(([cmd]) => cmd === "session_detail")).toBe(false);
  });

  it("processes a reply for a turn on the active connection", async () => {
    const { result } = mount({ activeConnectionIdRef: { current: "A" } });
    await waitForListen();
    seedTurn(result, { requestId: "req-1", connectionId: "A", sessionId: "sA", launchSessionId: "sA" });
    invoke.mockClear();
    emit({ kind: "reply", session_id: "sA" });
    expect(invoke.mock.calls.some(([cmd]) => cmd === "session_detail")).toBe(true);
  });
});

describe("useChatStream new-chat hero detach", () => {
  it("promotes a streaming new-chat turn to its real session so the hero frees up", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { requestId: "req-1", connectionId: "A", sessionId: null, launchSessionId: null });
    emit({ kind: "session_start", session_id: "S1" });
    expect(turnOf(result, "req-1").sessionId).toBe("S1");
    expect(turnOf(result, "req-1").launchSessionId).toBeNull();
    act(() => result.current.detachNewChatTurns("A"));
    expect(turnOf(result, "req-1").launchSessionId).toBe("S1");
  });

  it("falls back to the request id when the turn has no session id yet", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { requestId: "req-1", connectionId: "A", sessionId: null, launchSessionId: null });
    act(() => result.current.detachNewChatTurns("A"));
    expect(turnOf(result, "req-1").launchSessionId).toBe("req-1");
  });

  it("leaves new-chat turns on other connections untouched", async () => {
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { requestId: "a1", connectionId: "A", sessionId: null, launchSessionId: null });
    seedTurn(result, { requestId: "b1", connectionId: "B", sessionId: null, launchSessionId: null });
    act(() => result.current.detachNewChatTurns("A"));
    expect(turnOf(result, "a1").launchSessionId).toBe("a1");
    expect(turnOf(result, "b1").launchSessionId).toBeNull();
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
    seedTurn(result, { connectionId: "A", sessionId: "sess-1" });

    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(invoke).toHaveBeenCalledWith(
      "chat_events_since",
      expect.objectContaining({
        profile: "doc",
        sessionId: "sess-1",
        afterSeq: 0,
        connectionId: "A",
      }),
    );
    expect(notify).toHaveBeenCalledWith(
      expect.objectContaining({ variant: "info" }),
    );
    expect(turnOf(result)).toBeNull();
  });

  it("a recovered turn is dropped when its transcript fetch fails, with the failure surfaced", async () => {
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
      if (cmd === "session_detail") throw new Error("connection-disabled");
      return null;
    });
    const { result, notify } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });

    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    expect(turnOf(result)).toBeNull();
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ variant: "error" }));
  });

  it("a live done during a recovered turn's settle wait does not start a second transcript read", async () => {
    let detail = null;
    invoke.mockImplementation((cmd) => {
      if (cmd === "chat_events_since") {
        return Promise.resolve({
          exists: true,
          events: [
            { frame: { event: "session_start", session_id: "sess-1" } },
            { frame: { event: "assistant_delta", text: "ok" } },
            { frame: { event: "done", session_id: "sess-1" } },
          ],
        });
      }
      if (cmd === "session_detail") return new Promise((res, rej) => { detail = { res, rej }; });
      return Promise.resolve(null);
    });
    const { result } = mount();
    await waitForListen();
    seedTurn(result, { sessionId: "sess-1" });

    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    expect(invoke.mock.calls.filter(([cmd]) => cmd === "session_detail")).toHaveLength(1);
    expect(turnOf(result).settling).toBe(true);

    emit({ kind: "done", session_id: "sess-1" });
    await settle();
    expect(invoke.mock.calls.filter(([cmd]) => cmd === "session_detail")).toHaveLength(1);

    await act(async () => {
      detail.res({ id: "sess-1", turns: [] });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(turnOf(result)).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
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
