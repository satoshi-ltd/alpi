import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ loops: 0, reduce: false }));

vi.mock('react-native', () => {
  const View = ({ children, style }) => React.createElement('div', { 'data-opacity': style?.opacity, 'data-width': style?.width }, children);
  class Value {
    constructor(value) { this.value = value; }
    setValue(next) { this.value = next; }
    stopAnimation() {}
    interpolate() { return 0; }
  }
  const Animated = {
    Value,
    View,
    timing: () => ({}),
    sequence: () => ({}),
    loop: () => { h.loops += 1; return { start: () => {}, stop: () => {} }; },
  };
  return { Animated, Easing: { inOut: (fn) => fn, ease: 'ease' }, View };
});
vi.mock('../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { ink3: '#666', line: '#ddd', accent: '#a70' } }) }));

import { Dot } from './Dot';
import { SyncBar } from './SyncBar';

describe('looping motion honours reduce motion', () => {
  it('pulses a Dot only when motion is allowed', () => {
    h.loops = 0;
    h.reduce = false;
    render(<Dot color="#f00" pulse />);
    expect(h.loops).toBe(1);
    cleanup();
    h.loops = 0;
    h.reduce = true;
    const { container } = render(<Dot color="#f00" pulse />);
    expect(h.loops).toBe(0);
    expect(container.firstChild.getAttribute('data-opacity')).toBe('1');
  });

  it('sweeps the SyncBar only when motion is allowed, and shows a still bar otherwise', () => {
    h.loops = 0;
    h.reduce = false;
    render(<SyncBar syncing />);
    expect(h.loops).toBe(1);
    cleanup();
    h.loops = 0;
    h.reduce = true;
    const { container } = render(<SyncBar syncing />);
    expect(h.loops).toBe(0);
    expect(container.querySelector('[data-width="100%"]')).toBeTruthy();
  });
});
