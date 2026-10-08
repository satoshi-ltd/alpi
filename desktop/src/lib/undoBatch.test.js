import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createUndoBatch, deletedMessage, UNDO_WINDOW_MS } from "../../../common/undoBatch.mjs";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("deletedMessage", () => {
  it("names one row and counts a run", () => {
    expect(deletedMessage(1, "Backup failed")).toBe("Deleted “Backup failed”");
    expect(deletedMessage(3, "Backup failed")).toBe("Deleted 3 notifications");
  });
});

describe("createUndoBatch", () => {
  it("commits every entry together once the window ends", () => {
    const commit = vi.fn();
    const batch = createUndoBatch({ commit });
    expect(batch.add("a", { n: 1 })).toBe(1);
    vi.advanceTimersByTime(UNDO_WINDOW_MS - 1);
    expect(batch.add("b", { n: 2 })).toBe(2);
    vi.advanceTimersByTime(UNDO_WINDOW_MS - 1);
    expect(commit).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(commit).toHaveBeenCalledWith([{ n: 1 }, { n: 2 }]);
    expect(batch.size()).toBe(0);
  });

  it("a key added twice stays one entry", () => {
    const batch = createUndoBatch({ commit: vi.fn() });
    batch.add("a", { n: 1 });
    expect(batch.add("a", { n: 2 })).toBe(1);
    expect(batch.undoAll()).toEqual([{ n: 2 }]);
  });

  it("undoAll returns the pending entries and nothing commits", () => {
    const commit = vi.fn();
    const batch = createUndoBatch({ commit });
    batch.add("a", 1);
    batch.add("b", 2);
    expect(batch.undoAll()).toEqual([1, 2]);
    vi.advanceTimersByTime(UNDO_WINDOW_MS * 2);
    expect(commit).not.toHaveBeenCalled();
    expect(batch.undoAll()).toEqual([]);
  });

  it("an add while paused stays held until resume spends a full window", () => {
    const commit = vi.fn();
    const batch = createUndoBatch({ commit });
    batch.add("a", 1);
    batch.pause();
    batch.add("b", 2);
    vi.advanceTimersByTime(UNDO_WINDOW_MS * 4);
    expect(commit).not.toHaveBeenCalled();
    batch.resume();
    vi.advanceTimersByTime(UNDO_WINDOW_MS - 1);
    expect(commit).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(commit).toHaveBeenCalledWith([1, 2]);
  });

  it("an undo while paused leaves the next batch unpaused", () => {
    const commit = vi.fn();
    const batch = createUndoBatch({ commit });
    batch.add("a", 1);
    batch.pause();
    batch.undoAll();
    batch.add("b", 2);
    vi.advanceTimersByTime(UNDO_WINDOW_MS);
    expect(commit).toHaveBeenCalledWith([2]);
  });

  it("a custom window applies to its own add only", () => {
    const commit = vi.fn();
    const batch = createUndoBatch({ commit });
    batch.add("a", 1, { delayMs: 80 });
    vi.advanceTimersByTime(80);
    expect(commit).toHaveBeenCalledTimes(1);
    batch.add("b", 2);
    vi.advanceTimersByTime(80);
    expect(commit).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(UNDO_WINDOW_MS);
    expect(commit).toHaveBeenCalledTimes(2);
  });
});
