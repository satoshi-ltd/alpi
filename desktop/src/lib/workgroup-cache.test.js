import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  loadCachedMessages,
  saveCachedMessages,
  pruneCachedMessages,
  _resetPendingSaves,
} from "./workgroup-cache.js";

beforeEach(() => {
  localStorage.clear();
  _resetPendingSaves();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("debounced writes", () => {
  it("coalesces rapid saves into one localStorage write with the last value", () => {
    vi.useFakeTimers();
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    for (let i = 1; i <= 20; i += 1) {
      saveCachedMessages("conn-a", "doc", "wg-1", [{ seq: i }]);
    }
    expect(setItem).not.toHaveBeenCalled();
    // Reads see the pending value before the flush lands.
    expect(loadCachedMessages("conn-a", "doc", "wg-1")).toEqual([{ seq: 20 }]);
    vi.advanceTimersByTime(1100);
    expect(setItem).toHaveBeenCalledTimes(1);
    expect(loadCachedMessages("conn-a", "doc", "wg-1")).toEqual([{ seq: 20 }]);
    setItem.mockRestore();
  });

  it("prune cancels a pending save so it cannot resurrect a dropped workgroup", () => {
    vi.useFakeTimers();
    saveCachedMessages("conn-a", "doc", "wg-dead", [{ seq: 1 }]);
    pruneCachedMessages("conn-a", []);
    vi.advanceTimersByTime(2000);
    expect(loadCachedMessages("conn-a", "doc", "wg-dead")).toEqual([]);
  });
});

describe("save + load roundtrip", () => {
  it("persists and reads back", () => {
    saveCachedMessages("conn-a", "doc", "wg-1", [{ seq: 1 }, { seq: 2 }]);
    expect(loadCachedMessages("conn-a", "doc", "wg-1")).toEqual([
      { seq: 1 }, { seq: 2 },
    ]);
  });

  it("returns [] when the slot is empty", () => {
    expect(loadCachedMessages("conn-a", "doc", "wg-1")).toEqual([]);
  });

  it("returns [] on corrupt JSON instead of throwing", () => {
    localStorage.setItem("alpi.workgroup.cache.conn-a.doc.wg-1", "{nope");
    expect(loadCachedMessages("conn-a", "doc", "wg-1")).toEqual([]);
  });

  it("trims to the last 200 messages so localStorage never balloons", () => {
    const arr = Array.from({ length: 300 }, (_, i) => ({ seq: i }));
    saveCachedMessages("conn-a", "doc", "wg-1", arr);
    const back = loadCachedMessages("conn-a", "doc", "wg-1");
    expect(back).toHaveLength(200);
    expect(back[0].seq).toBe(100);
    expect(back[199].seq).toBe(299);
  });

  it("coerces a non-array input to []", () => {
    saveCachedMessages("conn-a", "doc", "wg-1", "not-an-array");
    expect(loadCachedMessages("conn-a", "doc", "wg-1")).toEqual([]);
  });
});

describe("pruneCachedMessages", () => {
  it("drops slots whose workgroup is no longer live for THIS connection", () => {
    saveCachedMessages("conn-a", "doc", "wg-keep", [{ seq: 1 }]);
    saveCachedMessages("conn-a", "doc", "wg-drop", [{ seq: 1 }]);
    pruneCachedMessages("conn-a", [{ profile: "doc", id: "wg-keep" }]);
    expect(loadCachedMessages("conn-a", "doc", "wg-keep")).toHaveLength(1);
    expect(loadCachedMessages("conn-a", "doc", "wg-drop")).toEqual([]);
  });

  it("never touches another connection's slots", () => {
    saveCachedMessages("conn-a", "doc", "wg-1", [{ seq: 1 }]);
    saveCachedMessages("conn-b", "doc", "wg-1", [{ seq: 2 }]);
    pruneCachedMessages("conn-a", []);
    expect(loadCachedMessages("conn-a", "doc", "wg-1")).toEqual([]);
    expect(loadCachedMessages("conn-b", "doc", "wg-1")).toEqual([{ seq: 2 }]);
  });

  it("no-op when connectionId is falsy", () => {
    saveCachedMessages("conn-a", "doc", "wg-1", [{ seq: 1 }]);
    pruneCachedMessages(null, []);
    expect(loadCachedMessages("conn-a", "doc", "wg-1")).toEqual([{ seq: 1 }]);
  });
});
