import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

import { BRAND_INK, FALLBACK_ACCENT } from '../../../common/shapes.mjs';
import { BUSY_DELAY_MS, BUSY_LABEL, BUSY_MIN_MS } from '../../../common/busy.mjs';
import { STILL } from '../../../common/agentMarks.mjs';
import { state as anim } from '../../tests/mocks/reanimated.js';

const h = vi.hoisted(() => ({ mode: 'light', reduce: false }));

vi.mock('react-native', () => {
  const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
  const View = ({ children, style, accessibilityRole, accessibilityLabel, accessible, pointerEvents, ...p }) =>
    React.createElement('div', { ...p, role: accessibilityRole, 'aria-label': accessibilityLabel, 'data-style': JSON.stringify(flat(style)) }, children);
  const Text = ({ children, style }) => React.createElement('span', { 'data-style': JSON.stringify(flat(style)) }, children);
  return { Text, View };
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
  Object.assign(h, { mode: 'light', reduce: false });
  anim.timings.length = 0;
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const mark = (root) => root.querySelector('[data-mark]');

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

  it.each(['light', 'dark'])('draws Twin in the flat brand ink of the %s theme, never a profile colour', (mode) => {
    h.mode = mode;
    const { container } = render(<Busy visible color={FALLBACK_ACCENT} accent={FALLBACK_ACCENT} />);
    expect(mark(container).getAttribute('data-mark')).toBe('alpi-twin');
    expect(mark(container).getAttribute('data-state')).toBe('busy');
    expect(container.querySelector('path').getAttribute('fill')).toBe(BRAND_INK[mode]);
    expect(container.innerHTML).not.toContain(FALLBACK_ACCENT);
  });

  it('turns and looks around in its busy loop on one clock', () => {
    render(<Busy visible />);
    expect(anim.timings).toHaveLength(1);
  });

  it('never draws below the smallest size Twin reads at', () => {
    const { container } = render(<Busy visible size={10} />);
    expect(container.querySelector('svg').getAttribute('width')).toBe('18');
    expect(mark(container).getAttribute('data-mark')).toBe('alpi-twin-small');
  });

  it('stands still in its busy expression with its words under reduced motion', () => {
    h.reduce = true;
    const { container, getByText } = render(<Busy visible label="Reaching the daemon" />);
    expect(anim.timings).toHaveLength(0);
    expect(STILL.busy[3][0]).toBe('look');
    expect(mark(container).getAttribute('data-state')).toBe('busy');
    expect(getByText('Reaching the daemon')).toBeTruthy();
  });
});
