import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StrictMode } from "react";
import { useSkeleton, useSkeletonPhase } from "./useSkeleton.js";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("useSkeleton", () => {
  it("stays hidden until the delay passes", () => {
    const { result } = renderHook(() => useSkeleton(true));
    act(() => vi.advanceTimersByTime(149));
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe(true);
  });

  it("never shows when loading ends inside the delay", () => {
    const { result, rerender } = renderHook(({ l }) => useSkeleton(l), { initialProps: { l: true } });
    act(() => vi.advanceTimersByTime(100));
    rerender({ l: false });
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current).toBe(false);
  });

  it("stays at least minShown once shown", () => {
    const { result, rerender } = renderHook(({ l }) => useSkeleton(l), { initialProps: { l: true } });
    act(() => vi.advanceTimersByTime(150));
    expect(result.current).toBe(true);
    act(() => vi.advanceTimersByTime(100));
    rerender({ l: false });
    act(() => vi.advanceTimersByTime(299));
    expect(result.current).toBe(true);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe(false);
  });

  it("hides at once when the minimum already elapsed", () => {
    const { result, rerender } = renderHook(({ l }) => useSkeleton(l), { initialProps: { l: true } });
    act(() => vi.advanceTimersByTime(150 + 500));
    rerender({ l: false });
    act(() => vi.advanceTimersByTime(0));
    expect(result.current).toBe(false);
  });

  it("honours custom delay and minShown", () => {
    const { result, rerender } = renderHook(({ l }) => useSkeleton(l, { delay: 10, minShown: 50 }), { initialProps: { l: true } });
    act(() => vi.advanceTimersByTime(10));
    expect(result.current).toBe(true);
    rerender({ l: false });
    act(() => vi.advanceTimersByTime(50));
    expect(result.current).toBe(false);
  });

  it("clears its timers on unmount and never updates state afterwards", () => {
    const { unmount } = renderHook(() => useSkeleton(true));
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
    const shown = renderHook(({ l }) => useSkeleton(l), { initialProps: { l: true } });
    act(() => vi.advanceTimersByTime(150));
    shown.rerender({ l: false });
    expect(vi.getTimerCount()).toBe(1);
    shown.unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("stays shown when loading returns during the hold and keeps the full minimum for the next end", () => {
    const { result, rerender } = renderHook(({ l }) => useSkeleton(l), { initialProps: { l: true } });
    act(() => vi.advanceTimersByTime(150));
    act(() => vi.advanceTimersByTime(100));
    rerender({ l: false });
    act(() => vi.advanceTimersByTime(100));
    rerender({ l: true });
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current).toBe(true);
    rerender({ l: false });
    act(() => vi.advanceTimersByTime(0));
    expect(result.current).toBe(false);
  });

  it("behaves the same under StrictMode", () => {
    const { result, rerender } = renderHook(({ l }) => useSkeleton(l), { initialProps: { l: true }, wrapper: StrictMode });
    act(() => vi.advanceTimersByTime(149));
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe(true);
    act(() => vi.advanceTimersByTime(100));
    rerender({ l: false });
    act(() => vi.advanceTimersByTime(299));
    expect(result.current).toBe(true);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe(false);
  });

  it("reports revealed only once bones were actually shown", () => {
    const { result, rerender } = renderHook(({ l }) => useSkeletonPhase(l), { initialProps: { l: true } });
    act(() => vi.advanceTimersByTime(100));
    rerender({ l: false });
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current).toEqual({ show: false, revealed: false });
    rerender({ l: true });
    act(() => vi.advanceTimersByTime(150));
    rerender({ l: false });
    act(() => vi.advanceTimersByTime(400));
    expect(result.current).toEqual({ show: false, revealed: true });
  });
});
