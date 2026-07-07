import { beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: (...a) => invokeMock(...a) }));

import {
  absoluteEnd,
  fetchFullSession,
  fetchSessionDetail,
  isDeltaBase,
  isSessionGone,
  mergeSessionTurns,
  normalizeSessionResult,
} from "./session-fetch.js";

beforeEach(() => invokeMock.mockReset());

const turn = (i) => ({ at: i, user: `u${i}`, assistant: `a${i}` });

describe("normalizeSessionResult", () => {
  it("unwraps the envelope with total/offset", () => {
    const res = normalizeSessionResult({ session: { id: "s" }, total_turns: 5, turns_offset: 2 });
    expect(res).toEqual({ session: { id: "s" }, totalTurns: 5, turnsOffset: 2, inFlight: false, kind: null });
  });

  it("reads kind from the envelope", () => {
    const res = normalizeSessionResult({ session: { id: "s" }, total_turns: 1, turns_offset: 0, kind: "workgroup" });
    expect(res.kind).toBe("workgroup");
  });

  it("treats a bare legacy session object as envelope-less", () => {
    const res = normalizeSessionResult({ id: "s", turns: [] });
    expect(res.totalTurns).toBeNull();
    expect(res.session.id).toBe("s");
    expect(res.inFlight).toBe(false);
  });

  it("reads in_flight true from the envelope", () => {
    const res = normalizeSessionResult({ session: { id: "s" }, in_flight: true });
    expect(res.inFlight).toBe(true);
  });
});

describe("isSessionGone", () => {
  it("flags deleted sessions and dead tokens, never transient or method errors", () => {
    expect(isSessionGone("alp -32004: not-found — no session 's1'")).toBe(true);
    expect(isSessionGone("alp -32000: auth-failed")).toBe(true);
    expect(isSessionGone("websocket read: Resource temporarily unavailable")).toBe(false);
    expect(isSessionGone("alp -32601: method-not-found")).toBe(false);
    expect(isSessionGone("connect ws://10.0.0.2:49200: refused")).toBe(false);
  });
});

describe("fetchFullSession", () => {
  it("fetches full when nothing is known", async () => {
    invokeMock.mockResolvedValueOnce({
      session: { id: "s", turns: [turn(0)] },
      total_turns: 1,
      turns_offset: 0,
    });
    const data = await fetchFullSession("work", "s");
    expect(data.turns).toHaveLength(1);
    expect(invokeMock).toHaveBeenCalledWith("session_detail", { profile: "work", id: "s" });
  });

  it("appends only the new turns when a full session is known", async () => {
    const known = { id: "s", turns: [turn(0), turn(1)] };
    invokeMock.mockResolvedValueOnce({
      session: { id: "s", turns: [turn(2)], cost_usd: 9 },
      total_turns: 3,
      turns_offset: 2,
    });
    const data = await fetchFullSession("work", "s", { known });
    expect(invokeMock).toHaveBeenCalledWith("session_detail", {
      profile: "work", id: "s", afterTurn: 2,
    });
    expect(data.turns.map((t) => t.user)).toEqual(["u0", "u1", "u2"]);
    expect(data.cost_usd).toBe(9);
  });

  it("never uses a persisted display-only tail as the slice base even with an offset", async () => {
    const known = { id: "s", partialTail: true, displayOnly: true, turnsOffset: 5, turns: [turn(5)] };
    invokeMock.mockResolvedValueOnce({
      session: { id: "s", turns: [turn(0)] },
      total_turns: 1,
      turns_offset: 0,
    });
    await fetchFullSession("work", "s", { known });
    expect(invokeMock).toHaveBeenCalledWith("session_detail", { profile: "work", id: "s" });
  });

  it("refetches full when the daemon reports fewer turns than known (session rewritten)", async () => {
    const known = { id: "s", turns: [turn(0), turn(1), turn(2)] };
    invokeMock
      .mockResolvedValueOnce({ session: { id: "s", turns: [] }, total_turns: 1, turns_offset: 1 })
      .mockResolvedValueOnce({
        session: { id: "s", turns: [turn(0)] },
        total_turns: 1,
        turns_offset: 0,
      });
    const data = await fetchFullSession("work", "s", { known });
    expect(data.turns).toHaveLength(1);
    expect(invokeMock).toHaveBeenCalledTimes(2);
  });

  it("accepts an old daemon's full response even when a slice was requested", async () => {
    const known = { id: "s", turns: [turn(0)] };
    invokeMock.mockResolvedValueOnce({ session: { id: "s", turns: [turn(0), turn(1)] } });
    const data = await fetchFullSession("work", "s", { known });
    expect(data.turns).toHaveLength(2);
    expect(invokeMock).toHaveBeenCalledTimes(1);
  });

  it("refetches full when the known base was captured in-flight (mutable tail)", async () => {
    const known = { id: "s", turns: [turn(0)], in_flight: true };
    invokeMock.mockResolvedValueOnce({
      session: { id: "s", turns: [turn(0), turn(1)] },
      total_turns: 2,
      turns_offset: 0,
    });
    const data = await fetchFullSession("work", "s", { known });
    expect(invokeMock).toHaveBeenCalledWith("session_detail", { profile: "work", id: "s" });
    expect(data.turns.map((t) => t.user)).toEqual(["u0", "u1"]);
  });

  it("ignores a known session whose id differs", async () => {
    const known = { id: "other", turns: [turn(0)] };
    invokeMock.mockResolvedValueOnce({
      session: { id: "s", turns: [turn(0)] },
      total_turns: 1,
      turns_offset: 0,
    });
    await fetchFullSession("work", "s", { known });
    expect(invokeMock).toHaveBeenCalledWith("session_detail", { profile: "work", id: "s" });
  });

  it("carries in_flight through onto the returned session on a full fetch", async () => {
    invokeMock.mockResolvedValueOnce({
      session: { id: "s", turns: [turn(0)] },
      total_turns: 1,
      turns_offset: 0,
      in_flight: true,
    });
    const data = await fetchFullSession("work", "s");
    expect(data.in_flight).toBe(true);
  });

  it("carries in_flight through onto the returned session on a merged fetch", async () => {
    const known = { id: "s", turns: [turn(0)] };
    invokeMock.mockResolvedValueOnce({
      session: { id: "s", turns: [turn(1)] },
      total_turns: 2,
      turns_offset: 1,
      in_flight: true,
    });
    const data = await fetchFullSession("work", "s", { known });
    expect(data.in_flight).toBe(true);
    expect(data.turns).toHaveLength(2);
  });

  it("defaults in_flight to false when the daemon omits it", async () => {
    invokeMock.mockResolvedValueOnce({ session: { id: "s", turns: [turn(0)] } });
    const data = await fetchFullSession("work", "s");
    expect(data.in_flight).toBe(false);
  });

  it("uses a server-sourced partial slice as delta base with an absolute afterTurn", async () => {
    const known = { id: "s", turns: [turn(5), turn(6)], turnsOffset: 5, totalTurns: 7, partialTail: true };
    invokeMock.mockResolvedValueOnce({
      session: { id: "s", turns: [turn(7)] },
      total_turns: 8,
      turns_offset: 7,
    });
    const data = await fetchFullSession("work", "s", { known });
    expect(invokeMock).toHaveBeenCalledWith("session_detail", {
      profile: "work", id: "s", afterTurn: 7,
    });
    expect(data.turns.map((t) => t.user)).toEqual(["u5", "u6", "u7"]);
    expect(data.turnsOffset).toBe(5);
    expect(data.totalTurns).toBe(8);
    expect(data.partialTail).toBe(true);
  });

  it("stamps envelope kind onto the returned session", async () => {
    invokeMock.mockResolvedValueOnce({
      session: { id: "s", turns: [turn(0)] },
      total_turns: 1,
      turns_offset: 0,
      kind: "chat",
    });
    const data = await fetchFullSession("work", "s");
    expect(data.kind).toBe("chat");
  });
});

describe("isDeltaBase", () => {
  it("accepts full sessions and server slices, rejects persisted tails", () => {
    expect(isDeltaBase({ id: "s", turns: [] })).toBe(true);
    expect(isDeltaBase({ id: "s", turns: [], partialTail: true, turnsOffset: 3 })).toBe(true);
    expect(isDeltaBase({ id: "s", turns: [], partialTail: true })).toBe(false);
    expect(isDeltaBase({ id: "s", turns: [], partialTail: true, turnsOffset: 3, displayOnly: true })).toBe(false);
    expect(isDeltaBase(null)).toBe(false);
    expect(isDeltaBase({ id: "s" })).toBe(false);
  });
});

describe("mergeSessionTurns with offsets", () => {
  it("appends against the absolute end of a partial slice", () => {
    const known = { id: "s", turns: [turn(3), turn(4)], turnsOffset: 3, partialTail: true };
    expect(absoluteEnd(known)).toBe(5);
    const res = normalizeSessionResult({
      session: { id: "s", turns: [turn(5)] }, total_turns: 6, turns_offset: 5,
    });
    const merged = mergeSessionTurns(known, res);
    expect(merged.turns.map((t) => t.user)).toEqual(["u3", "u4", "u5"]);
    expect(merged.turnsOffset).toBe(3);
    expect(merged.totalTurns).toBe(6);
  });

  it("rejects a slice that does not start at the absolute end", () => {
    const known = { id: "s", turns: [turn(3)], turnsOffset: 3 };
    const res = normalizeSessionResult({
      session: { id: "s", turns: [turn(9)] }, total_turns: 10, turns_offset: 9,
    });
    expect(mergeSessionTurns(known, res)).toBeNull();
  });
});

describe("fetchSessionDetail params", () => {
  it("passes tailTurns through", async () => {
    invokeMock.mockResolvedValueOnce({ session: { id: "s", turns: [] }, total_turns: 0, turns_offset: 0 });
    await fetchSessionDetail("work", "s", { tailTurns: 60 });
    expect(invokeMock).toHaveBeenCalledWith("session_detail", { profile: "work", id: "s", tailTurns: 60 });
  });

  it("passes beforeTurn/maxTurns through", async () => {
    invokeMock.mockResolvedValueOnce({ session: { id: "s", turns: [] }, total_turns: 0, turns_offset: 0 });
    await fetchSessionDetail("work", "s", { beforeTurn: 200, maxTurns: 100 });
    expect(invokeMock).toHaveBeenCalledWith("session_detail", {
      profile: "work", id: "s", beforeTurn: 200, maxTurns: 100,
    });
  });
});
