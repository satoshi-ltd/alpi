import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ loops: 0, reduce: false, bg: '#f0f0f0' }));

vi.mock('react-native', () => {
  const View = ({ children, style }) => React.createElement('div', { 'data-opacity': style?.opacity, 'data-width': style?.width, 'data-bg': style?.backgroundColor }, children);
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
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { ink: '#141414', ink3: '#666', line: '#ddd', accent: '#a70', bg: h.bg } }) }));

import { Dot } from './Dot';
import { SyncBar } from './SyncBar';
import { ACCENT_HEXES } from '../../../common/accents.mjs';
import { contrastRatio, nameTone } from '../../../common/name.mjs';
import { palettes } from '../../../common/tokens.mjs';

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

  it('paints the SyncBar in the profile hue toned for the ground, and in the brand ink otherwise', () => {
    h.reduce = true;
    h.bg = '#f0f0f0';
    const { container } = render(<SyncBar syncing color="#2cb3b5" />);
    expect(container.querySelector('[data-width="100%"]').getAttribute('data-bg')).toBe(nameTone('#2cb3b5', '#f0f0f0'));
    cleanup();
    const plain = render(<SyncBar syncing />);
    expect(plain.container.querySelector('[data-width="100%"]').getAttribute('data-bg')).toBe('#a70');
  });

  it.each(ACCENT_HEXES)('%s passes 3:1 on the light and the dark ground', (accent) => {
    h.reduce = true;
    for (const mode of ['light', 'dark']) {
      h.bg = palettes[mode].bg;
      const { container } = render(<SyncBar syncing color={accent} />);
      const tone = container.querySelector('[data-width="100%"]').getAttribute('data-bg');
      expect(contrastRatio(tone, palettes[mode].bg)).toBeGreaterThanOrEqual(3);
      cleanup();
    }
    h.bg = '#f0f0f0';
  });
});
