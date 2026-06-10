import { describe, it, expect, afterEach, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useCoalescedCallback } from "./useCoalescedCallback.js";

afterEach(() => {
  vi.useRealTimers();
});

describe("useCoalescedCallback", () => {
  it("coalesces a burst into one trailing call with the last args", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const { result } = renderHook(() => useCoalescedCallback(fn, 500));
    for (let i = 0; i < 10; i += 1) result.current(i);
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(550);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith(9);
  });

  it("max-wait fires even under continuous calls", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const { result } = renderHook(() => useCoalescedCallback(fn, 500, 5000));
    for (let i = 0; i < 30; i += 1) {
      result.current();
      vi.advanceTimersByTime(300);
    }
    expect(fn.mock.calls.length).toBeGreaterThanOrEqual(1);
  });

  it("without maxWait, continuous calls keep deferring", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const { result } = renderHook(() => useCoalescedCallback(fn, 500));
    for (let i = 0; i < 10; i += 1) {
      result.current();
      vi.advanceTimersByTime(300);
    }
    expect(fn).not.toHaveBeenCalled();
  });

  it("unmount drops the pending call", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const { result, unmount } = renderHook(() => useCoalescedCallback(fn, 500));
    result.current();
    unmount();
    vi.advanceTimersByTime(1000);
    expect(fn).not.toHaveBeenCalled();
  });
});
