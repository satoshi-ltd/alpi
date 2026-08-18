import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';

const h = vi.hoisted(() => ({ timings: [], calls: [] }));

vi.mock('react-native-gesture-handler', () => {
  const pan = {};
  for (const key of ['activeOffsetY', 'onUpdate', 'onEnd']) pan[key] = () => pan;
  return { Gesture: { Pan: () => pan } };
});

vi.mock('react-native-reanimated', () => ({
  default: {},
  Easing: { bezier: (...points) => `bezier(${points.join(',')})` },
  runOnJS: (fn) => fn,
  useAnimatedStyle: (fn) => fn(),
  useSharedValue: (initial) => React.useRef({ value: initial }).current,
  withTiming: (toValue, config) => {
    h.timings.push(toValue);
    h.calls.push({ to: toValue, ...config });
    return toValue;
  },
}));

import {
  DURATION_IN,
  DURATION_OUT,
  EASE_IN,
  EASE_OUT,
  UNMOUNT_BUFFER,
  useSheetGesture,
} from './useSheetGesture';

beforeEach(() => {
  h.timings.length = 0;
  h.calls.length = 0;
});

describe('useSheetGesture off-screen distance', () => {
  it('closes to 900 when the caller passes nothing', () => {
    renderHook(() => useSheetGesture(false, () => {}));
    expect(h.timings).toContain(900);
  });

  it('closes to the distance the caller passes', () => {
    renderHook(() => useSheetGesture(false, () => {}, 1294));
    expect(h.timings).toContain(1294);
    expect(h.timings).not.toContain(900);
  });

  it('parks a closed sheet at the passed distance instead of the default', () => {
    const { result } = renderHook(() => useSheetGesture(false, () => {}, 1294));
    expect(result.current.sheetStyle.transform[0].translateY).toBe(1294);
  });

  it('still animates an open sheet to zero', () => {
    renderHook(() => useSheetGesture(true, () => {}, 1294));
    expect(h.timings).toContain(0);
    expect(h.timings).not.toContain(1294);
  });

  it('re-parks at the new distance when the viewport changes under a closed sheet', () => {
    const { rerender } = renderHook(({ px }) => useSheetGesture(false, () => {}, px), {
      initialProps: { px: 1294 },
    });
    h.timings.length = 0;
    rerender({ px: 1056 });
    expect(h.timings).toContain(1056);
  });
});

describe('useSheetGesture easing', () => {
  const easings = (to) => h.calls.filter((c) => c.to === to).map((c) => c.easing);

  it('enters on the ease-out curve', () => {
    renderHook(() => useSheetGesture(true, () => {}, 1294));
    expect(easings(0)).toEqual([EASE_IN]);
    expect(EASE_IN).toBe('bezier(0.2,0.7,0.2,1)');
  });

  it('exits on the time-reverse of the entrance, not the entrance replayed backwards', () => {
    renderHook(() => useSheetGesture(false, () => {}, 1294));
    expect(easings(1294)).toEqual([EASE_OUT]);
    expect(EASE_OUT).toBe('bezier(0.8,0,0.8,0.3)');
    expect(EASE_OUT).not.toBe(EASE_IN);
  });

  it('fades the backdrop out on the same reversed curve as the sheet', () => {
    renderHook(() => useSheetGesture(false, () => {}, 1294));
    const backdrop = h.calls.filter((c) => c.to === 0);
    expect(backdrop.map((c) => c.easing)).toEqual([EASE_OUT]);
  });

  it('gives the exit the same duration as the entrance', () => {
    expect(DURATION_OUT).toBe(DURATION_IN);
    renderHook(() => useSheetGesture(false, () => {}, 1294));
    expect(h.calls.every((c) => c.duration === DURATION_OUT)).toBe(true);
  });
});

describe('useSheetGesture mount lifetime', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('mounts synchronously on open so the entrance has something to animate', () => {
    const { result } = renderHook(({ open }) => useSheetGesture(open, () => {}, 1294), {
      initialProps: { open: false },
    });
    expect(result.current.mounted).toBe(false);
  });

  it('stays mounted for the whole exit animation after open flips false', () => {
    const { result, rerender } = renderHook(({ open }) => useSheetGesture(open, () => {}, 1294), {
      initialProps: { open: true },
    });
    expect(result.current.mounted).toBe(true);

    rerender({ open: false });
    expect(result.current.mounted).toBe(true);

    act(() => vi.advanceTimersByTime(DURATION_OUT));
    expect(result.current.mounted).toBe(true);

    act(() => vi.advanceTimersByTime(UNMOUNT_BUFFER));
    expect(result.current.mounted).toBe(false);
  });

  it('cancels the teardown when the sheet is reopened mid-exit', () => {
    const { result, rerender } = renderHook(({ open }) => useSheetGesture(open, () => {}, 1294), {
      initialProps: { open: true },
    });
    rerender({ open: false });
    act(() => vi.advanceTimersByTime(100));
    rerender({ open: true });
    act(() => vi.advanceTimersByTime(DURATION_OUT + UNMOUNT_BUFFER));
    expect(result.current.mounted).toBe(true);
  });
});
