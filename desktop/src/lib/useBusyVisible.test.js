import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BUSY_DELAY_MS, BUSY_MIN_MS } from "../../../common/busy.mjs";
import { useBusyVisible, useReducedMotion } from "./useBusyVisible.js";

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  delete window.matchMedia;
});

describe("useBusyVisible", () => {
  it("turns visible only once the delay has passed", () => {
    const { result } = renderHook(({ active }) => useBusyVisible(active), { initialProps: { active: true } });
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS - 1));
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe(true);
  });

  it("drops a wait that ends inside the delay without ever showing it", () => {
    const { result, rerender } = renderHook(({ active }) => useBusyVisible(active), { initialProps: { active: true } });
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS - 50));
    rerender({ active: false });
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS + BUSY_MIN_MS));
    expect(result.current).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("holds the minimum time after the wait ends, then hides", () => {
    const { result, rerender } = renderHook(({ active }) => useBusyVisible(active), { initialProps: { active: true } });
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    rerender({ active: false });
    expect(result.current).toBe(true);
    act(() => vi.advanceTimersByTime(BUSY_MIN_MS - 1));
    expect(result.current).toBe(true);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe(false);
  });

  it("restarts the delay for a new wait after the last one hid", () => {
    const { result, rerender } = renderHook(({ active }) => useBusyVisible(active), { initialProps: { active: true } });
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    rerender({ active: false });
    act(() => vi.advanceTimersByTime(BUSY_MIN_MS));
    rerender({ active: true });
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    expect(result.current).toBe(true);
  });

  it("starts over, hidden, when the thing it waits for changes", () => {
    const { result, rerender } = renderHook(({ active, key }) => useBusyVisible(active, key), { initialProps: { active: true, key: "a" } });
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    expect(result.current).toBe(true);
    rerender({ active: false, key: "b" });
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(BUSY_MIN_MS));
    expect(result.current).toBe(false);
  });

  it("clears its timer on unmount", () => {
    const { unmount } = renderHook(() => useBusyVisible(true));
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("useReducedMotion", () => {
  it("is false without matchMedia and follows the media query when present", () => {
    expect(renderHook(() => useReducedMotion()).result.current).toBe(false);
    window.matchMedia = (query) => ({ matches: query === "(prefers-reduced-motion: reduce)", addEventListener() {}, removeEventListener() {} });
    expect(renderHook(() => useReducedMotion()).result.current).toBe(true);
  });

  it.each([
    ["addEventListener", (media, fn) => { media.addEventListener = (_, cb) => fn(cb); media.removeEventListener = () => {}; }],
    ["addListener", (media, fn) => { media.addListener = (cb) => fn(cb); media.removeListener = () => {}; }],
  ])("follows a change of the setting through %s", (_, wire) => {
    let fire = null;
    const media = { matches: false };
    wire(media, (cb) => { fire = cb; });
    window.matchMedia = () => media;
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
    media.matches = true;
    act(() => fire());
    expect(result.current).toBe(true);
  });
});
