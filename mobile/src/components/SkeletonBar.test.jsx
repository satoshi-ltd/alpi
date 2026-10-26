import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

const h = vi.hoisted(() => ({ reduce: false, started: 0, set: [], timings: [], init: [], style: null }));

vi.mock('react-native', () => ({
  Animated: {
    Value: class {
      constructor(v) { h.init.push(v); }
      setValue(v) { h.set.push(v); }
    },
    View: ({ style }) => {
      h.style = [style].flat(Infinity).filter(Boolean)[0];
      return React.createElement('div', { 'data-bg': h.style.backgroundColor });
    },
    timing: (_v, cfg) => { h.timings.push(cfg); return {}; },
    sequence: () => ({}),
    loop: () => ({ start: () => { h.started += 1; }, stop: () => {} }),
  },
}));
vi.mock('../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { hover: '#f4f4f4', line: '#ececec' } }) }));

const { SkeletonBar, STAGGER_MS } = await import('./SkeletonBar');

beforeEach(() => {
  vi.useFakeTimers();
  Object.assign(h, { reduce: false, started: 0, set: [], timings: [], init: [], style: null });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('SkeletonBar', () => {
  it('breathes on the line tone, never the hover tone', () => {
    const { container } = render(<SkeletonBar width={80} />);
    vi.runAllTimers();
    expect(h.started).toBe(1);
    expect(container.firstChild.dataset.bg).toBe('#ececec');
  });

  it('breathes 0.55 to 1 and back over 1.6 s', () => {
    render(<SkeletonBar width={80} />);
    expect(h.init).toEqual([0.55]);
    expect(h.timings.map((t) => [t.toValue, t.duration, t.useNativeDriver])).toEqual([[1, 800, true], [0.55, 800, true]]);
    expect(h.timings.reduce((n, t) => n + t.duration, 0)).toBe(1600);
  });

  it('starts after its delay so rows stagger by 90 ms', () => {
    render(<SkeletonBar width={80} delay={STAGGER_MS * 2} />);
    vi.advanceTimersByTime(STAGGER_MS * 2 - 1);
    expect(h.started).toBe(0);
    vi.advanceTimersByTime(1);
    expect(STAGGER_MS).toBe(90);
    expect(h.started).toBe(1);
  });

  it('rounds with the xs radius unless told otherwise', () => {
    render(<SkeletonBar width={80} />);
    expect(h.style.borderRadius).toBe(4);
    cleanup();
    render(<SkeletonBar width={80} radius={2} />);
    expect(h.style.borderRadius).toBe(2);
  });

  it('holds still at full opacity under reduced motion', () => {
    h.reduce = true;
    render(<SkeletonBar width={80} />);
    vi.runAllTimers();
    expect(h.started).toBe(0);
    expect(h.init).toEqual([1]);
    expect(h.set).toEqual([1]);
  });
});
