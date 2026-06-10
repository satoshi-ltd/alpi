import { describe, it, expect, afterEach, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useDebouncedCallback } from "./useDebouncedCallback.js";

afterEach(() => {
  vi.useRealTimers();
});

describe("useDebouncedCallback", () => {
  it("coalesces a burst into one trailing call", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(fn, 400));
    for (let i = 0; i < 10; i += 1) result.current(i);
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(450);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith(9);
  });

  it("max-wait fires even under a continuous stream of calls", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(fn, 400));
    // Calls every 200ms forever — trailing debounce alone would never fire.
    for (let i = 0; i < 12; i += 1) {
      result.current(i);
      vi.advanceTimersByTime(200);
    }
    expect(fn.mock.calls.length).toBeGreaterThanOrEqual(1);
  });

  it("unmount drops the pending call", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const { result, unmount } = renderHook(() => useDebouncedCallback(fn, 400));
    result.current();
    unmount();
    vi.advanceTimersByTime(1000);
    expect(fn).not.toHaveBeenCalled();
  });
});
