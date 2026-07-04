import { beforeEach, describe, expect, it } from "vitest";
import {
  loadCachedSession,
  saveCachedSession,
  removeCachedSession,
  invalidateSessionCache,
  _clearSessionCache,
} from "./session-cache.js";

function sessionWithTurns(id, n) {
  return {
    id,
    turns: Array.from({ length: n }, (_, i) => ({ at: i, user: `u${i}`, assistant: "a" })),
  };
}

beforeEach(() => {
  _clearSessionCache();
  localStorage.clear();
});

describe("session-cache", () => {
  it("memory hit returns the full session marked complete", () => {
    saveCachedSession("c1", "work", "s1", sessionWithTurns("s1", 3));
    const hit = loadCachedSession("c1", "work", "s1");
    expect(hit.complete).toBe(true);
    expect(hit.data.turns).toHaveLength(3);
  });

  it("localStorage survives a memory wipe as a display-only tail with absolute offset", () => {
    saveCachedSession("c1", "work", "s1", sessionWithTurns("s1", 100));
    _clearSessionCache();
    const hit = loadCachedSession("c1", "work", "s1");
    expect(hit.complete).toBe(false);
    expect(hit.data.partialTail).toBe(true);
    expect(hit.data.displayOnly).toBe(true);
    expect(hit.data.turnsOffset).toBe(40);
    expect(hit.data.turns).toHaveLength(60);
    expect(hit.data.turns[0].user).toBe("u40");
  });

  it("keeps at most 8 persisted sessions per (connection, profile)", () => {
    for (let i = 0; i < 10; i += 1) {
      saveCachedSession("c1", "work", `s${i}`, sessionWithTurns(`s${i}`, 1));
    }
    _clearSessionCache();
    expect(loadCachedSession("c1", "work", "s0")).toBeNull();
    expect(loadCachedSession("c1", "work", "s1")).toBeNull();
    expect(loadCachedSession("c1", "work", "s2")).not.toBeNull();
    expect(loadCachedSession("c1", "work", "s9")).not.toBeNull();
  });

  it("invalidateSessionCache drops memory for the connection but keeps the persisted tail", () => {
    saveCachedSession("c1", "work", "s1", sessionWithTurns("s1", 2));
    saveCachedSession("c2", "work", "s1", sessionWithTurns("s1", 2));
    invalidateSessionCache("c1");
    expect(loadCachedSession("c1", "work", "s1").complete).toBe(false);
    expect(loadCachedSession("c2", "work", "s1").complete).toBe(true);
  });

  it("ignores payloads without a turns array", () => {
    saveCachedSession("c1", "work", "s1", { id: "s1" });
    expect(loadCachedSession("c1", "work", "s1")).toBeNull();
  });

  it("removeCachedSession drops both the memory entry and the persisted tail", () => {
    saveCachedSession("c1", "work", "s1", sessionWithTurns("s1", 3));
    removeCachedSession("c1", "work", "s1");
    expect(loadCachedSession("c1", "work", "s1")).toBeNull();
    _clearSessionCache();
    expect(loadCachedSession("c1", "work", "s1")).toBeNull();
  });

  it("a partial slice in memory is reported incomplete", () => {
    const partial = { ...sessionWithTurns("s1", 5), turnsOffset: 10, partialTail: true };
    saveCachedSession("c1", "work", "s1", partial);
    const hit = loadCachedSession("c1", "work", "s1");
    expect(hit.complete).toBe(false);
    expect(hit.data.turnsOffset).toBe(10);
  });

  it("persisted tails of partial slices keep the absolute offset but are display-only", () => {
    const partial = { ...sessionWithTurns("s1", 5), turnsOffset: 10, totalTurns: 15, partialTail: true };
    saveCachedSession("c1", "work", "s1", partial);
    _clearSessionCache();
    const hit = loadCachedSession("c1", "work", "s1");
    expect(hit.data.partialTail).toBe(true);
    expect(hit.data.displayOnly).toBe(true);
    expect(hit.data.turnsOffset).toBe(10);
    expect(hit.data.totalTurns).toBeUndefined();
  });

  it("skips persistence when persist is false but keeps the memory copy", () => {
    saveCachedSession("c1", "work", "s1", sessionWithTurns("s1", 3), { persist: false });
    expect(loadCachedSession("c1", "work", "s1").complete).toBe(true);
    _clearSessionCache();
    expect(loadCachedSession("c1", "work", "s1")).toBeNull();
  });

  it("truncates oversized tool outputs and text so heavy sessions still persist", () => {
    const heavy = {
      id: "s1",
      turns: Array.from({ length: 60 }, (_, i) => ({
        at: i,
        user: `u${i}`,
        assistant: "x".repeat(20_000),
        tools: [{ tool_id: `t${i}`, output: "y".repeat(50_000) }],
      })),
    };
    saveCachedSession("c1", "work", "s1", heavy);
    expect(heavy.turns[0].assistant).toHaveLength(20_000);
    expect(heavy.turns[0].tools[0].output).toHaveLength(50_000);
    _clearSessionCache();
    const hit = loadCachedSession("c1", "work", "s1");
    expect(hit).not.toBeNull();
    const t = hit.data.turns[0];
    expect(t.assistant.length).toBeLessThanOrEqual(16_001);
    expect(t.tools[0].output.length).toBeLessThanOrEqual(4_001);
  });

  it("halves the persisted turn count when trimmed turns still exceed the budget", () => {
    const monster = {
      id: "s1",
      turns: Array.from({ length: 60 }, (_, i) => ({
        at: i,
        user: "u".repeat(15_000),
        assistant: "a".repeat(15_000),
      })),
    };
    saveCachedSession("c1", "work", "s1", monster);
    _clearSessionCache();
    const hit = loadCachedSession("c1", "work", "s1");
    expect(hit).not.toBeNull();
    expect(hit.data.turns.length).toBeLessThan(60);
    expect(hit.data.turns.at(-1).at).toBe(59);
    expect(hit.data.turnsOffset).toBe(60 - hit.data.turns.length);
  });
});
