import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { StrictMode } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';

import { useSkeleton } from './useSkeleton';

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const mount = (loading) => renderHook(({ on }) => useSkeleton(on, { delay: 150, minShown: 400 }), { initialProps: { on: loading } });
const tick = (ms) => act(() => { vi.advanceTimersByTime(ms); });

describe('useSkeleton', () => {
  it('shows nothing for the first 150 ms of a load', () => {
    const { result } = mount(true);
    tick(149);
    expect(result.current).toBe(false);
    tick(1);
    expect(result.current).toBe(true);
  });

  it('never shows when the load ends inside the delay', () => {
    const { result, rerender } = mount(true);
    tick(100);
    rerender({ on: false });
    tick(1000);
    expect(result.current).toBe(false);
  });

  it('stays at least 400 ms once shown', () => {
    const { result, rerender } = mount(true);
    tick(150);
    tick(100);
    rerender({ on: false });
    expect(result.current).toBe(true);
    tick(299);
    expect(result.current).toBe(true);
    tick(1);
    expect(result.current).toBe(false);
  });

  it('hides at once when the minimum has already elapsed', () => {
    const { result, rerender } = mount(true);
    tick(150);
    tick(500);
    rerender({ on: false });
    tick(0);
    expect(result.current).toBe(false);
  });

  it('clears its timers on unmount and never updates afterwards', () => {
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { unmount } = mount(true);
    tick(100);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
    tick(1000);
    expect(errors).not.toHaveBeenCalled();
    errors.mockRestore();
  });

  it('clears the pending hide timer on unmount', () => {
    const { rerender, unmount } = mount(true);
    tick(150);
    rerender({ on: false });
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('stays shown when loading flips back on during the hold and hides once the new load ends', () => {
    const { result, rerender } = mount(true);
    tick(150);
    tick(100);
    rerender({ on: false });
    tick(100);
    rerender({ on: true });
    tick(1000);
    expect(result.current).toBe(true);
    rerender({ on: false });
    tick(0);
    expect(result.current).toBe(false);
  });

  it('restarts the 150 ms delay when loading flips off and on again before the bones appear', () => {
    const { result, rerender } = mount(true);
    tick(100);
    rerender({ on: false });
    tick(10);
    rerender({ on: true });
    tick(149);
    expect(result.current).toBe(false);
    tick(1);
    expect(result.current).toBe(true);
  });

  it('behaves the same under StrictMode double effects', () => {
    const { result, rerender } = renderHook(({ on }) => useSkeleton(on, { delay: 150, minShown: 400 }), {
      initialProps: { on: true },
      wrapper: StrictMode,
    });
    tick(149);
    expect(result.current).toBe(false);
    tick(1);
    expect(result.current).toBe(true);
    tick(100);
    rerender({ on: false });
    tick(299);
    expect(result.current).toBe(true);
    tick(1);
    expect(result.current).toBe(false);
  });
});
