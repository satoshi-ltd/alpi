import { beforeEach, describe, expect, it, vi } from "vitest";

import { createSessionOpener, prependOlderTurns, sessionFromSlice } from "./session-open.js";
import { normalizeSessionResult } from "./session-fetch.js";

const turn = (i) => ({ at: i, user: `u${i}`, assistant: `a${i}` });
const turns = (from, to) => Array.from({ length: to - from }, (_, i) => turn(from + i));

function envelope(id, allTurns, offset, end, extra = {}) {
  return normalizeSessionResult({
    session: { id, turns: allTurns.slice(offset, end) },
    total_turns: allTurns.length,
    turns_offset: offset,
    kind: "chat",
    ...extra,
  });
}

describe("sessionFromSlice", () => {
  it("marks a sliced tail partial with offsets", () => {
    const res = envelope("s", turns(0, 10), 7, 10);
    const data = sessionFromSlice(res);
    expect(data.turnsOffset).toBe(7);
    expect(data.totalTurns).toBe(10);
    expect(data.partialTail).toBe(true);
    expect(data.kind).toBe("chat");
  });

  it("leaves a full response unmarked", () => {
    const res = envelope("s", turns(0, 3), 0, 3);
    const data = sessionFromSlice(res);
    expect(data.turnsOffset).toBeUndefined();
    expect(data.partialTail).toBeUndefined();
    expect(data.totalTurns).toBe(3);
  });
});

describe("prependOlderTurns", () => {
  const all = turns(0, 10);
  const partial = { id: "s", turns: all.slice(7), turnsOffset: 7, totalTurns: 10, partialTail: true };

  it("prepends a contiguous older chunk", () => {
    const res = envelope("s", all, 4, 7);
    const { data, action } = prependOlderTurns(partial, res);
    expect(action).toBe("applied");
    expect(data.turns.map((t) => t.user)).toEqual(["u4", "u5", "u6", "u7", "u8", "u9"]);
    expect(data.turnsOffset).toBe(4);
    expect(data.partialTail).toBe(true);
  });

  it("clears partial flags when the chunk reaches the beginning", () => {
    const res = envelope("s", all, 0, 7);
    const { data, action } = prependOlderTurns(partial, res);
    expect(action).toBe("applied");
    expect(data.turnsOffset).toBeUndefined();
    expect(data.partialTail).toBeUndefined();
    expect(data.turns).toHaveLength(10);
  });

  it("replaces outright when the daemon ships the full session", () => {
    const res = envelope("s", all, 0, 10);
    const { data, action } = prependOlderTurns(partial, res);
    expect(action).toBe("replace");
    expect(data.turns).toHaveLength(10);
    expect(data.partialTail).toBeUndefined();
  });

  it("requests a restart when the session shrank below the known end", () => {
    const res = normalizeSessionResult({
      session: { id: "s", turns: [] }, total_turns: 5, turns_offset: 5,
    });
    const { action } = prependOlderTurns(partial, res);
    expect(action).toBe("restart");
  });

  it("skips a non-contiguous chunk", () => {
    const res = envelope("s", all, 2, 5);
    const { data, action } = prependOlderTurns(partial, res);
    expect(action).toBe("skip");
    expect(data).toBe(partial);
  });

  it("skips when prev is already complete", () => {
    const full = { id: "s", turns: all };
    const res = envelope("s", all, 4, 7);
    expect(prependOlderTurns(full, res).action).toBe("skip");
  });
});

function harness({ cached = null, fetchDetail, fetchFull = vi.fn() } = {}) {
  const state = { data: undefined, sync: undefined, syncLog: [] };
  const opener = createSessionOpener({
    activeConnectionIdRef: { current: "conn-1" },
    sessionDataRef: {
      get current() {
        return state.data;
      },
    },
    setSessionData: (v) => {
      state.data = typeof v === "function" ? v(state.data) : v;
    },
    setSessionSync: (v) => {
      state.sync = v;
      state.syncLog.push(v);
    },
    isChatSessionData: (d) => d?.kind !== "workgroup",
    onGone: vi.fn(),
    onNonChat: vi.fn(),
    onError: vi.fn(),
    fetchDetail,
    fetchFull,
    loadCached: () => cached,
    saveCached: vi.fn(),
  });
  return { state, opener };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

describe("createSessionOpener", () => {
  beforeEach(() => vi.clearAllMocks());

  it("cold open: tail first, then backfills older chunks until complete", async () => {
    const all = turns(0, 250);
    const calls = [];
    const fetchDetail = vi.fn(async (_p, _s, opts) => {
      calls.push(opts);
      if (opts.tailTurns) return envelope("s", all, all.length - 60, all.length);
      const end = opts.beforeTurn;
      return envelope("s", all, Math.max(0, end - opts.maxTurns), end);
    });
    const { state, opener } = harness({ fetchDetail });
    opener.open("work", "s");
    await flush();
    expect(calls).toEqual([
      { tailTurns: 60 },
      { beforeTurn: 190, maxTurns: 100 },
      { beforeTurn: 90, maxTurns: 100 },
    ]);
    expect(state.data.turns).toHaveLength(250);
    expect(state.data.turnsOffset).toBeUndefined();
    expect(state.data.partialTail).toBeUndefined();
    expect(state.sync).toBeNull();
    expect(state.syncLog[0]).toEqual({ phase: "refresh" });
    expect(state.syncLog.some((s) => s?.phase === "backfill")).toBe(true);
  });

  it("small session: tail covers everything, no backfill requests", async () => {
    const all = turns(0, 5);
    const fetchDetail = vi.fn(async () => envelope("s", all, 0, 5));
    const { state, opener } = harness({ fetchDetail });
    opener.open("work", "s");
    await flush();
    expect(fetchDetail).toHaveBeenCalledTimes(1);
    expect(state.data.turns).toHaveLength(5);
    expect(state.sync).toBeNull();
  });

  it("persisted tail renders immediately but is never a delta base", async () => {
    const cachedTail = {
      data: { id: "s", turns: turns(3, 5), turnsOffset: 3, partialTail: true, displayOnly: true },
      complete: false,
    };
    const all = turns(0, 5);
    const fetchDetail = vi.fn(async (_p, _s, opts) => {
      expect(opts.tailTurns).toBe(60);
      return envelope("s", all, 0, 5);
    });
    const { state, opener } = harness({ cached: cachedTail, fetchDetail });
    opener.open("work", "s");
    expect(state.data).toEqual(cachedTail.data);
    await flush();
    expect(state.data.turns).toHaveLength(5);
  });

  it("memory full session goes through the delta path", async () => {
    const known = { id: "s", turns: turns(0, 5) };
    const fetchFull = vi.fn(async () => ({ id: "s", turns: turns(0, 6), in_flight: false }));
    const { state, opener } = harness({
      cached: { data: known, complete: true },
      fetchDetail: vi.fn(),
      fetchFull,
    });
    opener.open("work", "s");
    await flush();
    expect(fetchFull).toHaveBeenCalledWith("work", "s", { known });
    expect(state.data.turns).toHaveLength(6);
    expect(state.sync).toBeNull();
  });

  it("old daemon: tail request answered with a bare full session finishes in one shot", async () => {
    const fetchDetail = vi.fn(async () => normalizeSessionResult({ id: "s", turns: turns(0, 8) }));
    const { state, opener } = harness({ fetchDetail });
    opener.open("work", "s");
    await flush();
    expect(fetchDetail).toHaveBeenCalledTimes(1);
    expect(state.data.turns).toHaveLength(8);
    expect(state.data.partialTail).toBeUndefined();
  });

  it("non-chat sessions clear the view instead of rendering", async () => {
    const all = turns(0, 3);
    const fetchDetail = vi.fn(async () => envelope("s", all, 0, 3, { kind: "workgroup" }));
    const { state, opener } = harness({ fetchDetail });
    const onNonChat = vi.fn();
    const o = createSessionOpener({
      activeConnectionIdRef: { current: "conn-1" },
      setSessionData: (v) => {
        state.data = typeof v === "function" ? v(state.data) : v;
      },
      setSessionSync: () => {},
      isChatSessionData: (d) => d?.kind !== "workgroup",
      onNonChat,
      fetchDetail,
      loadCached: () => null,
      saveCached: vi.fn(),
    });
    o.open("work", "s");
    await flush();
    expect(onNonChat).toHaveBeenCalledWith("conn-1", "work", "s");
    expect(state.data).toBeNull();
  });

  it("cancel stops the backfill loop", async () => {
    const all = turns(0, 500);
    let resolveChunk;
    const fetchDetail = vi.fn(async (_p, _s, opts) => {
      if (opts.tailTurns) return envelope("s", all, 440, 500);
      return new Promise((r) => {
        resolveChunk = () => r(envelope("s", all, 340, 440));
      });
    });
    const { state, opener } = harness({ fetchDetail });
    const cancel = opener.open("work", "s");
    await flush();
    cancel();
    resolveChunk();
    await flush();
    expect(state.data.turns).toHaveLength(60);
    expect(fetchDetail).toHaveBeenCalledTimes(2);
  });

  it("gone sessions invoke onGone", async () => {
    const onGone = vi.fn();
    const fetchDetail = vi.fn(async () => {
      throw new Error("alp -32004: not-found");
    });
    const o = createSessionOpener({
      activeConnectionIdRef: { current: "conn-1" },
      setSessionData: () => {},
      setSessionSync: () => {},
      isChatSessionData: () => true,
      onGone,
      fetchDetail,
      loadCached: () => null,
      saveCached: vi.fn(),
    });
    o.open("work", "s");
    await flush();
    expect(onGone).toHaveBeenCalledWith("conn-1", "work", "s");
  });

  it("transport errors surface through onError and clear sync", async () => {
    const onError = vi.fn();
    let sync;
    const o = createSessionOpener({
      activeConnectionIdRef: { current: "conn-1" },
      setSessionData: () => {},
      setSessionSync: (v) => {
        sync = v;
      },
      isChatSessionData: () => true,
      onError,
      fetchDetail: vi.fn(async () => {
        throw new Error("websocket read: timeout");
      }),
      loadCached: () => null,
      saveCached: vi.fn(),
    });
    o.open("work", "s");
    await flush();
    expect(onError).toHaveBeenCalled();
    expect(sync).toBeNull();
  });

  it("repairs the view after a concurrent stale replace clobbers backfilled turns", async () => {
    const all = turns(0, 300);
    let clobbered = false;
    let stateRef;
    const fetchDetail = vi.fn(async (_p, _s, opts) => {
      if (opts.tailTurns) return envelope("s", all, 240, 300);
      const end = opts.beforeTurn;
      if (end === 140 && !clobbered) {
        clobbered = true;
        stateRef.data = {
          id: "s", turns: all.slice(240), turnsOffset: 240, totalTurns: 300, partialTail: true,
        };
      }
      return envelope("s", all, Math.max(0, end - opts.maxTurns), end);
    });
    const { state, opener } = harness({ fetchDetail });
    stateRef = state;
    opener.open("work", "s");
    await flush();
    expect(state.data.turns).toHaveLength(300);
    expect(state.data.turnsOffset).toBeUndefined();
    expect(state.data.partialTail).toBeUndefined();
    expect(state.sync).toBeNull();
  });

  it("restart mid-backfill refetches the full session", async () => {
    const all = turns(0, 200);
    const fetchDetail = vi.fn(async (_p, _s, opts) => {
      if (opts.tailTurns) return envelope("s", all, 140, 200);
      return normalizeSessionResult({
        session: { id: "s", turns: [] }, total_turns: 100, turns_offset: 100,
      });
    });
    const fetchFull = vi.fn(async () => ({ id: "s", turns: turns(0, 100), in_flight: false }));
    const { state, opener } = harness({ fetchDetail, fetchFull });
    opener.open("work", "s");
    await flush();
    expect(fetchFull).toHaveBeenCalledWith("work", "s");
    expect(state.data.turns).toHaveLength(100);
  });
});
