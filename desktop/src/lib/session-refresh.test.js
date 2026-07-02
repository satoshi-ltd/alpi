import { beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: (...a) => invokeMock(...a) }));

import { createSessionRefresher } from "./session-refresh.js";
import { loadCachedSession, saveCachedSession, _clearSessionCache } from "./session-cache.js";

function harness({ activeId = "A" } = {}) {
  const activeConnectionIdRef = { current: activeId };
  const sessionDataRef = { current: null };
  const setSessionData = vi.fn((next) => {
    sessionDataRef.current = typeof next === "function" ? next(sessionDataRef.current) : next;
  });
  const clearViewSession = vi.fn();
  const refresher = createSessionRefresher({
    activeConnectionIdRef,
    sessionDataRef,
    setSessionData,
    clearViewSession,
    isChatSessionData: () => true,
  });
  return { activeConnectionIdRef, sessionDataRef, setSessionData, clearViewSession, ...refresher };
}

beforeEach(() => {
  invokeMock.mockReset();
  _clearSessionCache();
  localStorage.clear();
});

const envelope = (turns) => ({
  session: { id: "s1", turns },
  total_turns: turns.length,
  turns_offset: 0,
});

describe("createSessionRefresher", () => {
  it("applies a successful refresh when the connection is unchanged", async () => {
    const h = harness();
    invokeMock.mockResolvedValueOnce(envelope([{ user: "u0", assistant: "a" }]));
    await h.refresh("work", "s1");
    expect(h.sessionDataRef.current.id).toBe("s1");
    expect(loadCachedSession("A", "work", "s1")).not.toBeNull();
  });

  it("a late success after a connection switch never touches the visible session", async () => {
    const h = harness();
    let resolve;
    invokeMock.mockImplementationOnce(() => new Promise((r) => { resolve = r; }));
    const pending = h.refresh("work", "s1");
    h.activeConnectionIdRef.current = "B";
    resolve(envelope([{ user: "u0", assistant: "a" }]));
    await pending;
    expect(h.setSessionData).not.toHaveBeenCalled();
    expect(loadCachedSession("A", "work", "s1")).not.toBeNull();
    expect(loadCachedSession("B", "work", "s1")).toBeNull();
  });

  it("a not-found on the live connection clears cache, view and visible session", async () => {
    const h = harness();
    h.sessionDataRef.current = { id: "s1", turns: [] };
    saveCachedSession("A", "work", "s1", { id: "s1", turns: [] });
    invokeMock.mockRejectedValueOnce("alp -32004: not-found — no session 's1'");
    await h.refresh("work", "s1");
    expect(loadCachedSession("A", "work", "s1")).toBeNull();
    expect(h.sessionDataRef.current).toBeNull();
    expect(h.clearViewSession).toHaveBeenCalledWith("work", "s1");
  });

  it("a late not-found from the OLD connection purges only that cache and leaves the new view alone", async () => {
    const h = harness();
    saveCachedSession("A", "work", "s1", { id: "s1", turns: [] });
    saveCachedSession("B", "work", "s1", { id: "s1", turns: [] });
    let reject;
    invokeMock.mockImplementationOnce(() => new Promise((_r, rj) => { reject = rj; }));
    const pending = h.refresh("work", "s1");
    h.activeConnectionIdRef.current = "B";
    h.sessionDataRef.current = { id: "s1", turns: [] };
    reject("alp -32004: not-found — no session 's1'");
    await pending;
    expect(loadCachedSession("A", "work", "s1")).toBeNull();
    expect(loadCachedSession("B", "work", "s1")).not.toBeNull();
    expect(h.sessionDataRef.current).not.toBeNull();
    expect(h.clearViewSession).not.toHaveBeenCalled();
  });

  it("a transient error leaves cache, view and session untouched", async () => {
    const h = harness();
    saveCachedSession("A", "work", "s1", { id: "s1", turns: [] });
    invokeMock.mockRejectedValueOnce("websocket read: timeout");
    await h.refresh("work", "s1");
    expect(loadCachedSession("A", "work", "s1")).not.toBeNull();
    expect(h.setSessionData).not.toHaveBeenCalled();
    expect(h.clearViewSession).not.toHaveBeenCalled();
  });

  it("skips non-chat sessions without caching or mutating state", async () => {
    const h = harness();
    const refresher = createSessionRefresher({
      activeConnectionIdRef: h.activeConnectionIdRef,
      sessionDataRef: h.sessionDataRef,
      setSessionData: h.setSessionData,
      clearViewSession: h.clearViewSession,
      isChatSessionData: () => false,
    });
    invokeMock.mockResolvedValueOnce(envelope([{ user: "[workgroup x]", assistant: "a" }]));
    await refresher.refresh("work", "s1");
    expect(h.setSessionData).not.toHaveBeenCalled();
    expect(loadCachedSession("A", "work", "s1")).toBeNull();
  });
});
