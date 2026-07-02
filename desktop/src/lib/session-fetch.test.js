import { beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: (...a) => invokeMock(...a) }));

import { fetchFullSession, isSessionGone, normalizeSessionResult } from "./session-fetch.js";

beforeEach(() => invokeMock.mockReset());

const turn = (i) => ({ at: i, user: `u${i}`, assistant: `a${i}` });

describe("normalizeSessionResult", () => {
  it("unwraps the envelope with total/offset", () => {
    const res = normalizeSessionResult({ session: { id: "s" }, total_turns: 5, turns_offset: 2 });
    expect(res).toEqual({ session: { id: "s" }, totalTurns: 5, turnsOffset: 2 });
  });

  it("treats a bare legacy session object as envelope-less", () => {
    const res = normalizeSessionResult({ id: "s", turns: [] });
    expect(res.totalTurns).toBeNull();
    expect(res.session.id).toBe("s");
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

  it("never uses a persisted partial tail as the slice base", async () => {
    const known = { id: "s", partialTail: true, turns: [turn(5)] };
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
});
