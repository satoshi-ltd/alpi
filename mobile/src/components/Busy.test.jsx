import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

import { ALPACA_FOLD, BRAND_INK, FALLBACK_ACCENT, foldFacets, foldTones } from '../../../common/folds.mjs';
import { BUSY_DELAY_MS, BUSY_LABEL, BUSY_MIN_MS, BUSY_WAVE_S, busyFacetDelays } from '../../../common/busy.mjs';
import { busyWaveRange } from '../lib/busyWave';

const h = vi.hoisted(() => ({ mode: 'light', reduce: false, ranges: [], timings: [], started: 0, stopped: 0 }));

vi.mock('react-native', () => {
  const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
  const View = ({ children, style, accessibilityRole, accessibilityLabel, accessible, ...p }) =>
    React.createElement('div', { ...p, role: accessibilityRole, 'aria-label': accessibilityLabel, 'data-style': JSON.stringify(flat(style)) }, children);
  const Text = ({ children, style }) => React.createElement('span', { 'data-style': JSON.stringify(flat(style)) }, children);
  class Value {
    constructor(v) { this.v = v; }
    setValue(v) { this.v = v; }
    interpolate(range) { h.ranges.push(range); return range; }
  }
  const Animated = {
    Value,
    View: ({ children, style, ...p }) => React.createElement('div', { ...p, 'data-animated': '' }, children),
    timing: (value, config) => { h.timings.push(config); return {}; },
    loop: () => ({ start: () => { h.started += 1; }, stop: () => { h.stopped += 1; } }),
  };
  return { Animated, Easing: { linear: 'linear' }, Text, View };
});

vi.mock('../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000000', ink2: '#333333', ink3: '#666666' },
    fonts: { sans: { regular: 'Geist_400Regular' }, mono: 'GeistMono_400Regular' },
    fontSizes: { sm: 13 },
    mode: h.mode,
  }),
}));

const { Busy } = await import('./Busy');

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] });
  Object.assign(h, { mode: 'light', reduce: false, ranges: [], timings: [], started: 0, stopped: 0 });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const fills = (root) => [...root.querySelectorAll('polygon')].map((p) => p.getAttribute('fill'));

describe('Busy', () => {
  it('stays off screen for the first 300 ms so a quick answer never flashes it', () => {
    const { container } = render(<Busy label="Reaching the daemon" />);
    act(() => { vi.advanceTimersByTime(BUSY_DELAY_MS - 1); });
    expect(container.querySelector('[role="progressbar"]')).toBeNull();
    act(() => { vi.advanceTimersByTime(1); });
    expect(container.querySelector('[role="progressbar"]')).not.toBeNull();
  });

  it('keeps its place in a page while it waits out the delay', () => {
    const { container } = render(<Busy fill label="Reaching the daemon" />);
    expect(container.querySelector('[role="progressbar"]')).toBeNull();
    expect(JSON.parse(container.firstChild.dataset.style).flex).toBe(1);
  });

  it('stays at least 400 ms once shown, even when the wait ends right after', () => {
    const { container, rerender } = render(<Busy active label="Opening the job" />);
    act(() => { vi.advanceTimersByTime(BUSY_DELAY_MS); });
    rerender(<Busy active={false} label="Opening the job" />);
    act(() => { vi.advanceTimersByTime(BUSY_MIN_MS - 1); });
    expect(container.querySelector('[role="progressbar"]')).not.toBeNull();
    act(() => { vi.advanceTimersByTime(1); });
    expect(container.querySelector('[role="progressbar"]')).toBeNull();
  });

  it('says what it waits for, in the sans face and the second ink, and names itself by those words', () => {
    const { container, getByText } = render(<Busy visible label="Reaching the daemon" />);
    const style = JSON.parse(getByText('Reaching the daemon').dataset.style);
    expect(style.fontFamily).toBe('Geist_400Regular');
    expect(style.color).toBe('#333333');
    expect(container.querySelector('[role="progressbar"]').getAttribute('aria-label')).toBe('Reaching the daemon');
  });

  it('is labelled Loading when it shows no words', () => {
    const { container } = render(<Busy visible />);
    expect(container.querySelector('[role="progressbar"]').getAttribute('aria-label')).toBe(BUSY_LABEL);
    expect(container.querySelector('span')).toBeNull();
  });

  it.each(['light', 'dark'])('draws the alpaca in the flat brand ink of the %s theme, never a profile colour', (mode) => {
    h.mode = mode;
    const { container } = render(<Busy visible color={FALLBACK_ACCENT} accent={FALLBACK_ACCENT} />);
    const drawn = fills(container);
    expect(drawn).toHaveLength(foldFacets(ALPACA_FOLD).length);
    expect(new Set(drawn)).toEqual(new Set(foldTones(BRAND_INK[mode])));
    expect(drawn).not.toContain(FALLBACK_ACCENT);
  });

  it('dims its facets from tail to head in one 1.6 s loop, opacity only', () => {
    const { container } = render(<Busy visible />);
    const delays = busyFacetDelays(foldFacets(ALPACA_FOLD).length);
    expect(h.ranges).toEqual(delays.map((d) => busyWaveRange(d)));
    expect(h.timings).toEqual([expect.objectContaining({ toValue: 1, duration: BUSY_WAVE_S * 1000, useNativeDriver: true })]);
    expect(h.started).toBe(1);
    expect(container.querySelectorAll('[data-animated]')).toHaveLength(delays.length);
  });

  it('never draws below the smallest size the alpaca reads at', () => {
    const { container } = render(<Busy visible size={10} />);
    expect(container.querySelector('svg').getAttribute('width')).toBe('18');
  });

  it('stands still with its words under reduced motion', () => {
    h.reduce = true;
    const { container, getByText } = render(<Busy visible label="Reaching the daemon" />);
    expect(h.started).toBe(0);
    expect(h.ranges).toEqual([]);
    expect(container.querySelector('[data-still]')).not.toBeNull();
    expect(container.querySelectorAll('[data-animated]')).toHaveLength(0);
    expect(getByText('Reaching the daemon')).toBeTruthy();
  });

  it('stops the wave when it leaves', () => {
    const view = render(<Busy visible />);
    view.unmount();
    expect(h.stopped).toBe(1);
  });
});
