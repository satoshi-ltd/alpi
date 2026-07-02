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

  it("localStorage survives a memory wipe as a partial tail", () => {
    saveCachedSession("c1", "work", "s1", sessionWithTurns("s1", 100));
    _clearSessionCache();
    const hit = loadCachedSession("c1", "work", "s1");
    expect(hit.complete).toBe(false);
    expect(hit.data.partialTail).toBe(true);
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
});
