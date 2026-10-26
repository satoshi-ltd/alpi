import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

const h = vi.hoisted(() => ({ reduce: false, init: [], set: [], timings: [], started: 0 }));

vi.mock('react-native', () => ({
  Animated: {
    Value: class {
      constructor(v) { h.init.push(v); }
      setValue(v) { h.set.push(v); }
    },
    View: ({ children }) => React.createElement('div', {}, children),
    timing: (_v, cfg) => { h.timings.push(cfg); return { start: () => { h.started += 1; }, stop: () => {} }; },
  },
}));
vi.mock('../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));

const { FadeIn } = await import('./FadeIn');

beforeEach(() => Object.assign(h, { reduce: false, init: [], set: [], timings: [], started: 0 }));
afterEach(cleanup);

describe('FadeIn', () => {
  it('fades content in from 0 to 1 over 120 ms on the native driver', () => {
    const { container } = render(<FadeIn>content</FadeIn>);
    expect(container.textContent).toBe('content');
    expect(h.init).toEqual([0]);
    expect(h.timings).toEqual([{ toValue: 1, duration: 120, useNativeDriver: true }]);
    expect(h.started).toBe(1);
  });

  it('shows content at once under reduced motion', () => {
    h.reduce = true;
    render(<FadeIn>content</FadeIn>);
    expect(h.init).toEqual([1]);
    expect(h.started).toBe(0);
    expect(h.timings).toEqual([]);
  });

  it('shows content at once when told not to animate', () => {
    render(<FadeIn animate={false}>content</FadeIn>);
    expect(h.init).toEqual([1]);
    expect(h.set).toEqual([1]);
    expect(h.started).toBe(0);
    expect(h.timings).toEqual([]);
  });
});
