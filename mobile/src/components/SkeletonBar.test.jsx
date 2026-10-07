import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

const h = vi.hoisted(() => ({ reduce: false, started: 0, set: [] }));

vi.mock('react-native', () => ({
  Animated: {
    Value: class {
      setValue(v) { h.set.push(v); }
    },
    View: ({ style }) => React.createElement('div', { 'data-bg': [style].flat(Infinity).filter(Boolean)[0].backgroundColor }),
    timing: () => ({}),
    sequence: () => ({}),
    loop: () => ({ start: () => { h.started += 1; }, stop: () => {} }),
  },
}));
vi.mock('../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { hover: '#f4f4f4' } }) }));

const { SkeletonBar } = await import('./SkeletonBar');

beforeEach(() => {
  vi.useFakeTimers();
  Object.assign(h, { reduce: false, started: 0, set: [] });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('SkeletonBar', () => {
  it('pulses in the neutral hover tone', () => {
    const { container } = render(<SkeletonBar width={80} />);
    vi.runAllTimers();
    expect(h.started).toBe(1);
    expect(container.firstChild.dataset.bg).toBe('#f4f4f4');
  });

  it('holds one still tone under reduced motion', () => {
    h.reduce = true;
    render(<SkeletonBar width={80} />);
    vi.runAllTimers();
    expect(h.started).toBe(0);
    expect(h.set).toEqual([0.6]);
  });
});
