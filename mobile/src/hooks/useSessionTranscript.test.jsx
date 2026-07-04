import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

import { EndpointContext } from "../lib/EndpointContext";
import {
  _resetSessionTranscriptStore,
  fromTail,
  mergeDelta,
  mergeOlder,
  normalizeSessionRead,
  useSessionTranscript,
} from "./useSessionTranscript";

beforeEach(() => {
  _resetSessionTranscriptStore();
});

const turn = (i) => ({ at: i, user: `u${i}`, assistant: `a${i}` });
const turns = (from, to) => Array.from({ length: to - from }, (_, i) => turn(from + i));

function envelope(allTurns, offset, end, extra = {}) {
  return {
    session: { id: "s1", turns: allTurns.slice(offset, end) },
    total_turns: allTurns.length,
    turns_offset: offset,
    ...extra,
  };
}

function wrapperWith(call) {
  const endpoint = { id: "ep1", name: "ep1" };
  return function Wrapper({ children }) {
    return (
      <EndpointContext.Provider value={{ endpoint, call }}>
        {children}
      </EndpointContext.Provider>
    );
  };
}

describe("merge helpers", () => {
  const all = turns(0, 100);
  const prev = { session: { id: "s1", turns: all.slice(60) }, turnsOffset: 60, totalTurns: 100, inFlight: false };

  it("mergeDelta appends contiguous new turns", () => {
    const grown = [...all, turn(100)];
    const res = normalizeSessionRead(envelope(grown, 100, 101));
    const next = mergeDelta(prev, res);
    expect(next.session.turns).toHaveLength(41);
    expect(next.turnsOffset).toBe(60);
    expect(next.totalTurns).toBe(101);
  });

  it("mergeDelta returns null when the session shrank", () => {
    const res = normalizeSessionRead({ session: { id: "s1", turns: [] }, total_turns: 50, turns_offset: 50 });
    expect(mergeDelta(prev, res)).toBeNull();
  });

  it("mergeDelta replaces outright on an envelope-less full response", () => {
    const res = normalizeSessionRead({ id: "s1", turns: all });
    const next = mergeDelta(prev, res);
    expect(next.session.turns).toHaveLength(100);
    expect(next.turnsOffset).toBe(0);
    expect(next.totalTurns).toBeNull();
  });

  it("mergeOlder prepends a contiguous older chunk", () => {
    const res = normalizeSessionRead(envelope(all, 30, 60));
    const next = mergeOlder(prev, res);
    expect(next.session.turns.map((t) => t.user)[0]).toBe("u30");
    expect(next.session.turns).toHaveLength(70);
    expect(next.turnsOffset).toBe(30);
  });

  it("mergeOlder replaces when a daemon without before_turn ships the full session", () => {
    const res = normalizeSessionRead(envelope(all, 0, 100));
    const next = mergeOlder(prev, res);
    expect(next.session.turns).toHaveLength(100);
    expect(next.turnsOffset).toBe(0);
  });

  it("mergeOlder ignores a non-contiguous chunk", () => {
    const res = normalizeSessionRead(envelope(all, 10, 30));
    expect(mergeOlder(prev, res)).toBeNull();
  });

  it("fromTail clamps offset to 0 for envelope-less responses", () => {
    expect(fromTail(normalizeSessionRead({ id: "s1", turns: [] })).turnsOffset).toBe(0);
  });
});

describe("useSessionTranscript", () => {
  it("fetches a tail first, then loads older chunks via before_turn", async () => {
    const all = turns(0, 200);
    const calls = [];
    const call = vi.fn(async (method, params) => {
      calls.push(params);
      if (params.tail_turns) return envelope(all, all.length - params.tail_turns, all.length);
      if (params.before_turn != null) {
        const end = params.before_turn;
        return envelope(all, Math.max(0, end - params.max_turns), end);
      }
      throw new Error(`unexpected params ${JSON.stringify(params)}`);
    });
    const { result } = renderHook(() => useSessionTranscript("doc", "s1"), {
      wrapper: wrapperWith(call),
    });
    await waitFor(() => expect(result.current.data?.turns).toHaveLength(60));
    expect(calls[0]).toEqual({ profile: "doc", id: "s1", tail_turns: 60 });
    expect(result.current.turnsOffset).toBe(140);
    expect(result.current.hasMore).toBe(true);

    await act(() => result.current.loadOlder());
    expect(calls[1]).toEqual({ profile: "doc", id: "s1", before_turn: 140, max_turns: 30 });
    expect(result.current.data.turns).toHaveLength(90);
    expect(result.current.turnsOffset).toBe(110);
  });

  it("refresh() fetches only the delta after the known end", async () => {
    const all = turns(0, 100);
    let grown = all;
    const call = vi.fn(async (_m, params) => {
      if (params.tail_turns) return envelope(grown, grown.length - 60, grown.length);
      if (params.after_turn != null) return envelope(grown, params.after_turn, grown.length);
      throw new Error("unexpected");
    });
    const { result } = renderHook(() => useSessionTranscript("doc", "s1"), {
      wrapper: wrapperWith(call),
    });
    await waitFor(() => expect(result.current.data?.turns).toHaveLength(60));

    grown = [...all, turn(100), turn(101)];
    await act(() => result.current.refresh());
    expect(call).toHaveBeenLastCalledWith("host.session.read", {
      profile: "doc", id: "s1", after_turn: 100,
    });
    expect(result.current.data.turns).toHaveLength(62);
    expect(result.current.totalTurns).toBe(102);
  });

  it("a rewritten (shrunk) session falls back to a fresh tail", async () => {
    const all = turns(0, 100);
    let current = all;
    const call = vi.fn(async (_m, params) => {
      if (params.tail_turns) return envelope(current, Math.max(0, current.length - 60), current.length);
      if (params.after_turn != null) {
        return envelope(current, Math.min(params.after_turn, current.length), current.length);
      }
      throw new Error("unexpected");
    });
    const { result } = renderHook(() => useSessionTranscript("doc", "s1"), {
      wrapper: wrapperWith(call),
    });
    await waitFor(() => expect(result.current.data?.turns).toHaveLength(60));

    current = turns(0, 50);
    await act(() => result.current.refresh());
    expect(result.current.data.turns).toHaveLength(50);
    expect(result.current.turnsOffset).toBe(0);
    expect(result.current.totalTurns).toBe(50);
  });

  it("ancient daemons without the envelope keep working with full refetches", async () => {
    const call = vi.fn(async () => ({ id: "s1", turns: turns(0, 5), model: "m" }));
    const { result } = renderHook(() => useSessionTranscript("doc", "s1"), {
      wrapper: wrapperWith(call),
    });
    await waitFor(() => expect(result.current.data?.turns).toHaveLength(5));
    expect(result.current.totalTurns).toBeNull();
    expect(result.current.hasMore).toBe(false);

    await act(() => result.current.refresh());
    expect(call).toHaveBeenLastCalledWith("host.session.read", {
      profile: "doc", id: "s1", tail_turns: 60,
    });
  });

  it("daemons with tail_turns but no before_turn resolve loadOlder with the full transcript", async () => {
    const all = turns(0, 200);
    const call = vi.fn(async (_m, params) => {
      if (params.tail_turns) return envelope(all, 140, 200);
      return envelope(all, 0, 200);
    });
    const { result } = renderHook(() => useSessionTranscript("doc", "s1"), {
      wrapper: wrapperWith(call),
    });
    await waitFor(() => expect(result.current.data?.turns).toHaveLength(60));
    await act(() => result.current.loadOlder());
    expect(result.current.data.turns).toHaveLength(200);
    expect(result.current.hasMore).toBe(false);
  });

  it("remounting reuses the accumulated store and refreshes via delta", async () => {
    const all = turns(0, 100);
    const call = vi.fn(async (_m, params) => {
      if (params.tail_turns) return envelope(all, 40, 100);
      if (params.after_turn != null) return envelope(all, params.after_turn, all.length);
      throw new Error("unexpected");
    });
    const first = renderHook(() => useSessionTranscript("doc", "s1"), {
      wrapper: wrapperWith(call),
    });
    await waitFor(() => expect(first.result.current.data?.turns).toHaveLength(60));
    first.unmount();

    const second = renderHook(() => useSessionTranscript("doc", "s1"), {
      wrapper: wrapperWith(call),
    });
    expect(second.result.current.data?.turns).toHaveLength(60);
    await waitFor(() => expect(call).toHaveBeenLastCalledWith("host.session.read", {
      profile: "doc", id: "s1", after_turn: 100,
    }));
  });

  it("exposes inFlight from the latest read", async () => {
    const all = turns(0, 10);
    const call = vi.fn(async () => envelope(all, 0, 10, { in_flight: true }));
    const { result } = renderHook(() => useSessionTranscript("doc", "s1"), {
      wrapper: wrapperWith(call),
    });
    await waitFor(() => expect(result.current.inFlight).toBe(true));
  });

  it("auth failure clears the session", async () => {
    const call = vi.fn(async () => {
      throw new Error("auth-failed");
    });
    const { result } = renderHook(() => useSessionTranscript("doc", "s1"), {
      wrapper: wrapperWith(call),
    });
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.data).toBeNull();
  });

  it("a refresh requested mid-flight queues one follow-up delta instead of joining the stale read", async () => {
    const all = turns(0, 100);
    const grown = [...all, turn(100)];
    let resolveTail;
    const call = vi.fn((_m, params) => {
      if (params.tail_turns) {
        return new Promise((resolve) => {
          resolveTail = () => resolve(envelope(all, 40, 100));
        });
      }
      if (params.after_turn != null) {
        return Promise.resolve(envelope(grown, params.after_turn, grown.length));
      }
      throw new Error("unexpected");
    });
    const { result } = renderHook(() => useSessionTranscript("doc", "s1"), {
      wrapper: wrapperWith(call),
    });
    await waitFor(() => expect(call).toHaveBeenCalledTimes(1));

    // The turn that triggered these refreshes was saved AFTER the tail read started.
    act(() => {
      result.current.refresh();
      result.current.refresh();
    });
    await act(async () => {
      resolveTail();
    });

    await waitFor(() => expect(result.current.data?.turns).toHaveLength(61));
    expect(result.current.totalTurns).toBe(101);
    expect(call).toHaveBeenCalledTimes(2);
    expect(call).toHaveBeenLastCalledWith("host.session.read", {
      profile: "doc", id: "s1", after_turn: 100,
    });
  });

  it("concurrent loadOlder calls collapse into one request", async () => {
    const all = turns(0, 200);
    let olderCalls = 0;
    const call = vi.fn(async (_m, params) => {
      if (params.tail_turns) return envelope(all, 140, 200);
      olderCalls += 1;
      return envelope(all, params.before_turn - params.max_turns, params.before_turn);
    });
    const { result } = renderHook(() => useSessionTranscript("doc", "s1"), {
      wrapper: wrapperWith(call),
    });
    await waitFor(() => expect(result.current.data?.turns).toHaveLength(60));
    await act(() => Promise.all([result.current.loadOlder(), result.current.loadOlder()]));
    expect(olderCalls).toBe(1);
  });
});
